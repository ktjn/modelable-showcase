import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getPatient } from '../api/patients'
import { PatientDetail } from './PatientDetail'

vi.mock('../api/patients', () => ({
  getPatient: vi.fn(),
}))

const getPatientMock = vi.mocked(getPatient)

function renderPage(id: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/patients/${id}`]}>
        <Routes>
          <Route path="/patients/:id" element={<PatientDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PatientDetail rendering', () => {
  beforeEach(() => {
    getPatientMock.mockReset()
  })

  it('renders patient fields once the API responds', async () => {
    getPatientMock.mockResolvedValue({
      patientId: 'p-1',
      legalName: 'Ada Lovelace',
      preferredName: 'Ada',
      dateOfBirth: '1815-12-10',
      contact: { email: 'ada@example.com', phone: '555-0100' },
      address: { street: '1 Clinic Way', city: 'Springfield', postalCode: '00000', country: 'US' },
      preferredLanguage: 'en',
      createdAt: '2026-01-01T00:00:00Z',
    } as never)

    renderPage('p-1')

    expect(await screen.findByRole('heading', { name: 'Ada Lovelace' })).toBeInTheDocument()
    expect(getPatientMock).toHaveBeenCalledWith('p-1')
    expect(screen.getByText('p-1')).toBeInTheDocument()
    expect(screen.getByText('Ada')).toBeInTheDocument()
    expect(screen.getByText('ada@example.com')).toBeInTheDocument()
    expect(screen.getByText('555-0100')).toBeInTheDocument()
    expect(screen.getByText('1 Clinic Way, Springfield 00000, US')).toBeInTheDocument()
  })

  it('renders placeholders for absent optional fields', async () => {
    getPatientMock.mockResolvedValue({
      patientId: 'p-2',
      legalName: 'Grace Hopper',
      dateOfBirth: '1906-12-09',
      contact: {},
      preferredLanguage: 'en',
      createdAt: '2026-01-01T00:00:00Z',
    } as never)

    renderPage('p-2')

    expect(await screen.findByRole('heading', { name: 'Grace Hopper' })).toBeInTheDocument()
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(3)
  })

  it('shows an error message when the API request fails', async () => {
    getPatientMock.mockRejectedValue(new Error('patient p-404 not found'))

    renderPage('p-404')

    expect(await screen.findByRole('alert')).toHaveTextContent('patient p-404 not found')
  })
})
