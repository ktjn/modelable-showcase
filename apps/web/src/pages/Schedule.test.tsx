import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cancelAppointment, createAppointment, getDailySchedule, rescheduleAppointment } from '../api/appointments'
import { startEncounter, updateEncounterStatus } from '../api/encounters'
import { Schedule } from './Schedule'

vi.mock('../api/appointments', () => ({
  getDailySchedule: vi.fn(),
  createAppointment: vi.fn(),
  rescheduleAppointment: vi.fn(),
  cancelAppointment: vi.fn(),
}))
vi.mock('../api/encounters', () => ({
  startEncounter: vi.fn(),
  updateEncounterStatus: vi.fn(),
  addObservation: vi.fn(),
}))

const getDailyScheduleMock = vi.mocked(getDailySchedule)
const createAppointmentMock = vi.mocked(createAppointment)
const rescheduleAppointmentMock = vi.mocked(rescheduleAppointment)
const cancelAppointmentMock = vi.mocked(cancelAppointment)
const startEncounterMock = vi.mocked(startEncounter)
const updateEncounterStatusMock = vi.mocked(updateEncounterStatus)

const APPOINTMENT = {
  appointmentId: 'a-1',
  patientId: 'p-1',
  practitionerId: 'prac-1',
  scheduledDate: '2026-09-01',
  slot: { start: '09:00:00', end: '09:30:00' },
  status: 'requested',
  createdAt: '2026-08-01T00:00:00Z',
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <Schedule />
    </QueryClientProvider>,
  )
}

describe('Schedule rendering', () => {
  beforeEach(() => {
    getDailyScheduleMock.mockReset()
    createAppointmentMock.mockReset()
    cancelAppointmentMock.mockReset()
    startEncounterMock.mockReset()
    updateEncounterStatusMock.mockReset()
  })

  it('renders the appointments returned by the API', async () => {
    getDailyScheduleMock.mockResolvedValue([APPOINTMENT] as never)
    renderPage()

    expect(await screen.findByText(/patient p-1/)).toBeInTheDocument()
    expect(screen.getByText(/practitioner prac-1/)).toBeInTheDocument()
    expect(screen.getByText(/status requested/)).toBeInTheDocument()
  })

  it('shows a message when there are no appointments', async () => {
    getDailyScheduleMock.mockResolvedValue([])
    renderPage()

    expect(await screen.findByText('No appointments for this day.')).toBeInTheDocument()
  })
})

describe('Schedule create-appointment form validation and request mapping', () => {
  beforeEach(() => {
    getDailyScheduleMock.mockReset()
    getDailyScheduleMock.mockResolvedValue([])
    createAppointmentMock.mockReset()
  })

  it('rejects submission with no patient or practitioner id', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('No appointments for this day.')

    await user.click(screen.getByRole('button', { name: 'Book appointment' }))

    expect(await screen.findByText('Patient ID and practitioner ID are required.')).toBeInTheDocument()
    expect(createAppointmentMock).not.toHaveBeenCalled()
  })

  it('submits a generated-shape AppointmentCreateInput', async () => {
    const user = userEvent.setup()
    createAppointmentMock.mockResolvedValue(APPOINTMENT as never)
    renderPage()
    await screen.findByText('No appointments for this day.')

    await user.type(screen.getByLabelText('Patient ID'), 'p-1')
    await user.type(screen.getByLabelText('Practitioner ID'), 'prac-1')
    await user.click(screen.getByRole('button', { name: 'Book appointment' }))

    await waitFor(() => expect(createAppointmentMock).toHaveBeenCalledTimes(1))
    const [request] = createAppointmentMock.mock.calls[0]
    expect(request).toMatchObject({
      patientId: 'p-1',
      practitionerId: 'prac-1',
      status: 'requested',
      slot: { start: '09:00:00', end: '09:30:00' },
    })
    expect(typeof request.appointmentId).toBe('string')
  })
})

describe('Schedule appointment and encounter actions', () => {
  beforeEach(() => {
    getDailyScheduleMock.mockReset()
    getDailyScheduleMock.mockResolvedValue([APPOINTMENT] as never)
    rescheduleAppointmentMock.mockReset()
    cancelAppointmentMock.mockReset()
    startEncounterMock.mockReset()
    updateEncounterStatusMock.mockReset()
  })

  it('reschedules an appointment', async () => {
    const user = userEvent.setup()
    rescheduleAppointmentMock.mockResolvedValue({ ...APPOINTMENT, scheduledDate: '2026-09-02' } as never)
    renderPage()

    const row = (await screen.findByText(/patient p-1/)).closest('li') as HTMLElement
    await user.click(within(row).getByRole('button', { name: 'Reschedule' }))
    const dateInput = within(row).getByLabelText('Date')
    await user.clear(dateInput)
    await user.type(dateInput, '2026-09-02')
    await user.click(within(row).getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(rescheduleAppointmentMock).toHaveBeenCalledWith(
        'a-1',
        expect.objectContaining({ scheduledDate: '2026-09-02' }),
      ),
    )
  })

  it('cancels an appointment', async () => {
    const user = userEvent.setup()
    cancelAppointmentMock.mockResolvedValue({ ...APPOINTMENT, status: 'cancelled' } as never)
    renderPage()

    const row = (await screen.findByText(/patient p-1/)).closest('li') as HTMLElement
    await user.click(within(row).getByRole('button', { name: 'Cancel appointment' }))

    await waitFor(() => expect(cancelAppointmentMock).toHaveBeenCalledWith('a-1'))
  })

  it('starts an encounter, then completes it', async () => {
    const user = userEvent.setup()
    startEncounterMock.mockResolvedValue({
      encounterId: 'e-1',
      patientId: 'p-1',
      practitionerId: 'prac-1',
      status: 'in_progress',
      startedAt: '2026-09-01T09:00:00Z',
      createdAt: '2026-09-01T09:00:00Z',
    } as never)
    updateEncounterStatusMock.mockResolvedValue({
      encounterId: 'e-1',
      patientId: 'p-1',
      practitionerId: 'prac-1',
      status: 'completed',
      startedAt: '2026-09-01T09:00:00Z',
      endedAt: '2026-09-01T09:30:00Z',
      createdAt: '2026-09-01T09:00:00Z',
    } as never)
    renderPage()

    const row = (await screen.findByText(/patient p-1/)).closest('li') as HTMLElement
    await user.click(within(row).getByRole('button', { name: 'Start encounter' }))

    expect(await within(row).findByText('Encounter in progress.')).toBeInTheDocument()
    expect(startEncounterMock).toHaveBeenCalledWith(
      expect.objectContaining({ patientId: 'p-1', practitionerId: 'prac-1', appointmentId: 'a-1' }),
    )

    await user.click(within(row).getByRole('button', { name: 'Complete encounter' }))

    await waitFor(() => expect(updateEncounterStatusMock).toHaveBeenCalledWith('e-1', 'completed'))
    expect(await within(row).findByText('Encounter completed.')).toBeInTheDocument()
  })
})
