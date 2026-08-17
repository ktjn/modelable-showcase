import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getClinicAnalytics } from '../api/analytics'
import { Analytics } from './Analytics'

vi.mock('../api/analytics', () => ({
  getClinicAnalytics: vi.fn(),
}))

const getClinicAnalyticsMock = vi.mocked(getClinicAnalytics)

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <Analytics />
    </QueryClientProvider>,
  )
}

describe('Analytics rendering', () => {
  beforeEach(() => {
    getClinicAnalyticsMock.mockReset()
  })

  it('renders totals and breakdowns from the ClickHouse-backed endpoint', async () => {
    getClinicAnalyticsMock.mockResolvedValue({
      appointmentsPerDay: [{ day: '2026-09-01', appointmentCount: 3 }],
      billedTotal: '125.00',
      paidTotal: '75.00',
      practitionerAppointmentCounts: [{ practitionerId: 'prac-1', appointmentCount: 2 }],
    })

    renderPage()

    expect(await screen.findByText('125.00')).toBeInTheDocument()
    expect(screen.getByText('75.00')).toBeInTheDocument()
    expect(screen.getByText('2026-09-01: 3')).toBeInTheDocument()
    expect(screen.getByText('prac-1: 2')).toBeInTheDocument()
  })

  it('renders empty-state messages with no activity', async () => {
    getClinicAnalyticsMock.mockResolvedValue({
      appointmentsPerDay: [],
      billedTotal: '0.00',
      paidTotal: '0.00',
      practitionerAppointmentCounts: [],
    })

    renderPage()

    expect(await screen.findAllByText('No appointment activity yet.')).toHaveLength(2)
  })

  it('shows an error message when the request fails', async () => {
    getClinicAnalyticsMock.mockRejectedValue(new Error('analytics unavailable'))

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('analytics unavailable')
  })
})
