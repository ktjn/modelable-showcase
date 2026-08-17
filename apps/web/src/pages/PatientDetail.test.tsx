import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { addPayment, createInvoice } from '../api/billing'
import { getPatient } from '../api/patients'
import { getPatientSummary } from '../api/summary'
import { PatientDetail } from './PatientDetail'

vi.mock('../api/patients', () => ({
  getPatient: vi.fn(),
}))
vi.mock('../api/summary', () => ({
  getPatientSummary: vi.fn(),
}))
vi.mock('../api/billing', () => ({
  createInvoice: vi.fn(),
  addPayment: vi.fn(),
}))

const getPatientMock = vi.mocked(getPatient)
const getPatientSummaryMock = vi.mocked(getPatientSummary)
const createInvoiceMock = vi.mocked(createInvoice)
const addPaymentMock = vi.mocked(addPayment)

const EMPTY_SUMMARY = {
  patientId: 'p-1',
  legalName: 'Ada Lovelace',
  preferredName: null,
  dateOfBirth: '1815-12-10',
  preferredLanguage: 'en',
  appointmentCount: 0,
  encounterCount: 0,
  observationCount: 0,
  invoiceCount: 0,
  totalInvoiced: null,
  totalPaid: null,
  outstanding: null,
  lastEncounterAt: null,
}

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
    getPatientSummaryMock.mockReset()
    getPatientSummaryMock.mockResolvedValue(EMPTY_SUMMARY)
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

  it('renders the billing summary from the aggregation endpoint', async () => {
    getPatientMock.mockResolvedValue({ patientId: 'p-1', legalName: 'Ada Lovelace', contact: {} } as never)
    getPatientSummaryMock.mockResolvedValue({
      ...EMPTY_SUMMARY,
      invoiceCount: 2,
      totalInvoiced: '250.00',
      totalPaid: '125.00',
      outstanding: '125.00',
    })

    renderPage('p-1')

    expect(await screen.findByText('250.00')).toBeInTheDocument()
    expect(screen.getAllByText('125.00')).toHaveLength(2)
    expect(getPatientSummaryMock).toHaveBeenCalledWith('p-1')
  })
})

describe('PatientDetail invoice creation form validation and request mapping', () => {
  beforeEach(() => {
    getPatientMock.mockReset()
    getPatientMock.mockResolvedValue({ patientId: 'p-1', legalName: 'Ada Lovelace', contact: {} } as never)
    getPatientSummaryMock.mockReset()
    getPatientSummaryMock.mockResolvedValue(EMPTY_SUMMARY)
    createInvoiceMock.mockReset()
  })

  it('rejects submission with no description or amount', async () => {
    const user = userEvent.setup()
    renderPage('p-1')
    await screen.findByRole('heading', { name: 'Ada Lovelace' })

    const description = screen.getByLabelText('Description')
    await user.clear(description)
    await user.click(screen.getByRole('button', { name: 'Create invoice' }))

    expect(await screen.findByText('Description and a positive amount are required.')).toBeInTheDocument()
    expect(createInvoiceMock).not.toHaveBeenCalled()
  })

  it('submits a generated-shape InvoiceCreateInput with a computed total', async () => {
    const user = userEvent.setup()
    createInvoiceMock.mockResolvedValue({
      invoiceId: 'inv-1',
      patientId: 'p-1',
      lines: [],
      subtotal: '100.00',
      tax: '25.00',
      total: '125.00',
      status: 'issued',
      createdAt: '2026-09-01T00:00:00Z',
    } as never)
    renderPage('p-1')
    await screen.findByRole('heading', { name: 'Ada Lovelace' })

    await user.type(screen.getByLabelText('Amount'), '100.00')
    const tax = screen.getByLabelText('Tax')
    await user.clear(tax)
    await user.type(tax, '25.00')
    await user.click(screen.getByRole('button', { name: 'Create invoice' }))

    await waitFor(() => expect(createInvoiceMock).toHaveBeenCalledTimes(1))
    const [request] = createInvoiceMock.mock.calls[0]
    expect(request).toMatchObject({
      patientId: 'p-1',
      subtotal: '100.00',
      tax: '25.00',
      total: '125.00',
      status: 'issued',
    })
    expect(typeof request.invoiceId).toBe('string')
  })
})

describe('PatientDetail payment action', () => {
  beforeEach(() => {
    getPatientMock.mockReset()
    getPatientMock.mockResolvedValue({ patientId: 'p-1', legalName: 'Ada Lovelace', contact: {} } as never)
    getPatientSummaryMock.mockReset()
    getPatientSummaryMock.mockResolvedValue(EMPTY_SUMMARY)
    createInvoiceMock.mockReset()
    addPaymentMock.mockReset()
  })

  it('records a payment against a session-created invoice', async () => {
    const user = userEvent.setup()
    createInvoiceMock.mockResolvedValue({
      invoiceId: 'inv-1',
      patientId: 'p-1',
      lines: [],
      subtotal: '100.00',
      tax: '0.00',
      total: '100.00',
      status: 'issued',
      createdAt: '2026-09-01T00:00:00Z',
    } as never)
    addPaymentMock.mockResolvedValue({
      paymentId: 'pay-1',
      invoiceId: 'inv-1',
      amount: '100.00',
      method: 'card',
      receivedAt: '2026-09-02T00:00:00Z',
    })
    renderPage('p-1')
    await screen.findByRole('heading', { name: 'Ada Lovelace' })

    await user.type(screen.getByLabelText('Amount'), '100.00')
    await user.click(screen.getByRole('button', { name: 'Create invoice' }))
    await screen.findByText(/Invoice inv-1/)

    await user.click(screen.getByRole('button', { name: 'Record payment' }))

    await waitFor(() => expect(addPaymentMock).toHaveBeenCalledWith('inv-1', expect.objectContaining({ amount: '100.00', method: 'card' })))
    expect(await screen.findByText('Payment recorded for invoice inv-1.')).toBeInTheDocument()
  })
})
