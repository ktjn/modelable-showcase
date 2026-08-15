import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from './App'

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

  it('renders the patients route, which is built on the generated Patient-domain types', () => {
    renderApp('/patients')
    expect(screen.getByRole('heading', { name: 'Patients' })).toBeInTheDocument()
    expect(screen.getByText(/front-desk@modelable-clinic.example/)).toBeInTheDocument()
  })

  it('renders the patient detail route with a route param', () => {
    renderApp('/patients/patient-123')
    expect(screen.getByRole('heading', { name: 'Patient patient-123' })).toBeInTheDocument()
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
