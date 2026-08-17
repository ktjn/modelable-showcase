import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./api/patients', () => ({
  searchPatients: vi.fn().mockResolvedValue([]),
  getPatient: vi.fn().mockResolvedValue({
    patientId: 'patient-123',
    legalName: 'Ada Lovelace',
    dateOfBirth: '1815-12-10',
    contact: {},
    preferredLanguage: 'en',
    createdAt: '2026-01-01T00:00:00Z',
  }),
  createPatient: vi.fn(),
}))

function renderApp(initialPath = '/') {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('App shell', () => {
  it('renders navigation for every required route', () => {
    renderApp()
    expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: 'Patients' })).toHaveAttribute('href', '/patients')
    expect(screen.getByRole('link', { name: 'Schedule' })).toHaveAttribute('href', '/schedule')
    expect(screen.getByRole('link', { name: 'Analytics' })).toHaveAttribute('href', '/analytics')
  })

  it('renders the home route by default', () => {
    renderApp('/')
    expect(screen.getByRole('heading', { name: 'Modelable Clinic' })).toBeInTheDocument()
  })

  it('renders the patients route, which searches the generated Patient-domain API', () => {
    renderApp('/patients')
    expect(screen.getByRole('heading', { name: 'Patients' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'New patient' })).toHaveAttribute('href', '/patients/new')
  })

  it('renders the patient detail route with a route param', async () => {
    renderApp('/patients/patient-123')
    expect(await screen.findByRole('heading', { name: 'Ada Lovelace' })).toBeInTheDocument()
  })

  it('renders the schedule route', () => {
    renderApp('/schedule')
    expect(screen.getByRole('heading', { name: 'Schedule' })).toBeInTheDocument()
  })

  it('renders the analytics route', () => {
    renderApp('/analytics')
    expect(screen.getByRole('heading', { name: 'Analytics' })).toBeInTheDocument()
  })
})
