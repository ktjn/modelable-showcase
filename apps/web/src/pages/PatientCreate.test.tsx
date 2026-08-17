import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPatient } from '../api/patients'
import { PatientCreate } from './PatientCreate'

vi.mock('../api/patients', () => ({
  createPatient: vi.fn(),
}))

const createPatientMock = vi.mocked(createPatient)

function renderPage() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/patients/new']}>
        <Routes>
          <Route path="/patients/new" element={<PatientCreate />} />
          <Route path="/patients/:id" element={<div>Patient detail page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PatientCreate form validation', () => {
  beforeEach(() => {
    createPatientMock.mockReset()
  })

  it('rejects submission with no legal name, no date of birth, and no contact method', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: 'Create patient' }))

    expect(await screen.findByText('Legal name is required.')).toBeInTheDocument()
    expect(screen.getByText('Date of birth is required.')).toBeInTheDocument()
    expect(screen.getByText('Provide an email or a phone number.')).toBeInTheDocument()
    expect(createPatientMock).not.toHaveBeenCalled()
  })

  it('rejects an invalid email address', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByLabelText('Legal name'), 'Ada Lovelace')
    await user.type(screen.getByLabelText('Date of birth'), '1990-01-01')
    await user.type(screen.getByLabelText('Email'), 'not-an-email')
    await user.click(screen.getByRole('button', { name: 'Create patient' }))

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument()
    expect(createPatientMock).not.toHaveBeenCalled()
  })

  it('accepts a phone number in place of an email', async () => {
    const user = userEvent.setup()
    createPatientMock.mockResolvedValue({
      patientId: 'p-1',
      legalName: 'Ada Lovelace',
      dateOfBirth: '1990-01-01',
      contact: { phone: '555-0100' },
      preferredLanguage: 'en',
      createdAt: '2026-01-01T00:00:00Z',
    } as never)
    renderPage()

    await user.type(screen.getByLabelText('Legal name'), 'Ada Lovelace')
    await user.type(screen.getByLabelText('Date of birth'), '1990-01-01')
    await user.type(screen.getByLabelText('Phone'), '555-0100')
    await user.click(screen.getByRole('button', { name: 'Create patient' }))

    await waitFor(() => expect(createPatientMock).toHaveBeenCalledTimes(1))
  })
})

describe('PatientCreate API request mapping', () => {
  beforeEach(() => {
    createPatientMock.mockReset()
  })

  it('submits a generated-shape PatientCreateInput, omitting fields the form left blank', async () => {
    const user = userEvent.setup()
    createPatientMock.mockResolvedValue({ patientId: 'p-1' } as never)
    renderPage()

    await user.type(screen.getByLabelText('Legal name'), 'Ada Lovelace')
    await user.type(screen.getByLabelText('Preferred name'), 'Ada')
    await user.type(screen.getByLabelText('Date of birth'), '1990-01-01')
    await user.type(screen.getByLabelText('Email'), 'ada@example.com')
    await user.click(screen.getByRole('button', { name: 'Create patient' }))

    await waitFor(() => expect(createPatientMock).toHaveBeenCalledTimes(1))
    const [request] = createPatientMock.mock.calls[0]
    expect(request).toMatchObject({
      legalName: 'Ada Lovelace',
      preferredName: 'Ada',
      dateOfBirth: '1990-01-01',
      contact: { email: 'ada@example.com', phone: undefined },
      preferredLanguage: 'en',
    })
    expect(typeof request.patientId).toBe('string')
    expect(request.patientId.length).toBeGreaterThan(0)
  })

  it('navigates to the new patient detail page on success', async () => {
    const user = userEvent.setup()
    createPatientMock.mockResolvedValue({ patientId: 'new-patient-id' } as never)
    renderPage()

    await user.type(screen.getByLabelText('Legal name'), 'Ada Lovelace')
    await user.type(screen.getByLabelText('Date of birth'), '1990-01-01')
    await user.type(screen.getByLabelText('Email'), 'ada@example.com')
    await user.click(screen.getByRole('button', { name: 'Create patient' }))

    expect(await screen.findByText('Patient detail page')).toBeInTheDocument()
  })
})
