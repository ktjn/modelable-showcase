import type { AppointmentReply } from '@generated/scheduling.AppointmentReply.v1'
import type { EncounterReply } from '@generated/clinical.EncounterReply.v1'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import {
  cancelAppointment,
  createAppointment,
  getDailySchedule,
  rescheduleAppointment,
  type AppointmentCreateInput,
} from '../api/appointments'
import { addObservation, startEncounter, updateEncounterStatus } from '../api/encounters'
import { ModelableGuide } from '../components/ModelableGuide'

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

function ObservationForm({ encounterId }: { encounterId: string }) {
  const [code, setCode] = useState('temperature')
  const [temperature, setTemperature] = useState('')
  const [pulse, setPulse] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [savedCount, setSavedCount] = useState(0)

  const mutation = useMutation({
    mutationFn: () =>
      addObservation(encounterId, {
        code,
        temperatureCelsius: temperature ? Number(temperature) : undefined,
        pulseBpm: pulse ? Number(pulse) : undefined,
        recordedAt: new Date().toISOString(),
      }),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!temperature && !pulse) {
      setError('Enter at least a temperature or a pulse reading.')
      return
    }
    setError(null)
    mutation.mutate(undefined, {
      onSuccess: () => {
        setTemperature('')
        setPulse('')
        setSavedCount((count) => count + 1)
      },
    })
  }

  return (
    <form onSubmit={handleSubmit}>
      <label>
        Vital sign
        <select value={code} onChange={(event) => setCode(event.target.value)}>
          <option value="temperature">Temperature</option>
          <option value="blood_pressure">Blood pressure</option>
          <option value="pulse">Pulse</option>
        </select>
      </label>
      <label>
        Temperature (°C)
        <input value={temperature} onChange={(event) => setTemperature(event.target.value)} />
      </label>
      <label>
        Pulse (bpm)
        <input value={pulse} onChange={(event) => setPulse(event.target.value)} />
      </label>
      <button type="submit" disabled={mutation.isPending}>
        Add observation
      </button>
      {error && <p role="alert">{error}</p>}
      {mutation.isError && (
        <p role="alert">{mutation.error instanceof Error ? mutation.error.message : 'Failed to add observation.'}</p>
      )}
      {savedCount > 0 && <p>{savedCount} observation(s) recorded.</p>}
    </form>
  )
}

function RescheduleForm({ appointment, onDone }: { appointment: AppointmentReply; onDone: () => void }) {
  const [scheduledDate, setScheduledDate] = useState(appointment.scheduledDate)
  const [start, setStart] = useState(appointment.slot.start)
  const [end, setEnd] = useState(appointment.slot.end)
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => rescheduleAppointment(appointment.appointmentId, { scheduledDate, slot: { start, end } }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['schedule'] })
      onDone()
    },
  })

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <label>
        Date
        <input type="date" value={scheduledDate} onChange={(event) => setScheduledDate(event.target.value)} />
      </label>
      <label>
        Start
        <input type="time" step={1} value={start} onChange={(event) => setStart(event.target.value)} />
      </label>
      <label>
        End
        <input type="time" step={1} value={end} onChange={(event) => setEnd(event.target.value)} />
      </label>
      <button type="submit" disabled={mutation.isPending}>
        Save
      </button>
      <button type="button" onClick={onDone}>
        Cancel edit
      </button>
      {mutation.isError && (
        <p role="alert">{mutation.error instanceof Error ? mutation.error.message : 'Failed to reschedule.'}</p>
      )}
    </form>
  )
}

interface ScheduleRowProps {
  appointment: AppointmentReply
  encounter: EncounterReply | undefined
  onEncounterStarted: (appointmentId: string, encounter: EncounterReply) => void
  onEncounterUpdated: (appointmentId: string, encounter: EncounterReply) => void
}

function ScheduleRow({ appointment, encounter, onEncounterStarted, onEncounterUpdated }: ScheduleRowProps) {
  const [isRescheduling, setIsRescheduling] = useState(false)
  const queryClient = useQueryClient()

  const cancelMutation = useMutation({
    mutationFn: () => cancelAppointment(appointment.appointmentId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['schedule'] }),
  })

  const startEncounterMutation = useMutation({
    mutationFn: () =>
      startEncounter({
        encounterId: crypto.randomUUID(),
        patientId: appointment.patientId as unknown as string,
        practitionerId: appointment.practitionerId,
        appointmentId: appointment.appointmentId,
        startedAt: new Date().toISOString(),
      }),
    onSuccess: (started) => onEncounterStarted(appointment.appointmentId, started),
  })

  const completeEncounterMutation = useMutation({
    mutationFn: () => {
      if (!encounter) throw new Error('no encounter to complete')
      return updateEncounterStatus(encounter.encounterId, 'completed')
    },
    onSuccess: (updated) => onEncounterUpdated(appointment.appointmentId, updated),
  })

  const isCancelled = appointment.status === 'cancelled'

  return (
    <li>
      <p>
        <strong>{appointment.slot.start}</strong> - {appointment.slot.end} · patient{' '}
        {appointment.patientId as unknown as string} · practitioner {appointment.practitionerId} · status{' '}
        {appointment.status}
      </p>

      {isRescheduling ? (
        <RescheduleForm appointment={appointment} onDone={() => setIsRescheduling(false)} />
      ) : (
        !isCancelled && <button onClick={() => setIsRescheduling(true)}>Reschedule</button>
      )}

      {!isCancelled && (
        <button onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}>
          Cancel appointment
        </button>
      )}
      {cancelMutation.isError && (
        <p role="alert">{cancelMutation.error instanceof Error ? cancelMutation.error.message : 'Cancel failed.'}</p>
      )}

      {!isCancelled && !encounter && (
        <button onClick={() => startEncounterMutation.mutate()} disabled={startEncounterMutation.isPending}>
          Start encounter
        </button>
      )}
      {startEncounterMutation.isError && (
        <p role="alert">
          {startEncounterMutation.error instanceof Error
            ? startEncounterMutation.error.message
            : 'Failed to start encounter.'}
        </p>
      )}

      {encounter && encounter.status === 'in_progress' && (
        <>
          <p>Encounter in progress.</p>
          <button onClick={() => completeEncounterMutation.mutate()} disabled={completeEncounterMutation.isPending}>
            Complete encounter
          </button>
          <ObservationForm encounterId={encounter.encounterId} />
        </>
      )}
      {encounter && encounter.status === 'completed' && <p>Encounter completed.</p>}
    </li>
  )
}

export function Schedule() {
  const [date, setDate] = useState(today())
  const [practitioner, setPractitioner] = useState('')
  const [submitted, setSubmitted] = useState({ date: today(), practitioner: '' })
  const [encounters, setEncounters] = useState<Record<string, EncounterReply>>({})

  const [newPatientId, setNewPatientId] = useState('')
  const [newPractitionerId, setNewPractitionerId] = useState('')
  const [newStart, setNewStart] = useState('09:00:00')
  const [newEnd, setNewEnd] = useState('09:30:00')
  const [createError, setCreateError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['schedule', submitted.date, submitted.practitioner],
    queryFn: () => getDailySchedule({ date: submitted.date, practitioner: submitted.practitioner || undefined }),
  })

  const createMutation = useMutation({
    mutationFn: (request: AppointmentCreateInput) => createAppointment(request),
    onSuccess: () => {
      setNewPatientId('')
      setNewPractitionerId('')
      void queryClient.invalidateQueries({ queryKey: ['schedule'] })
    },
  })

  function handleFilterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitted({ date, practitioner: practitioner.trim() })
  }

  function handleCreateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!newPatientId.trim() || !newPractitionerId.trim()) {
      setCreateError('Patient ID and practitioner ID are required.')
      return
    }
    setCreateError(null)
    createMutation.mutate({
      appointmentId: crypto.randomUUID(),
      patientId: newPatientId.trim(),
      practitionerId: newPractitionerId.trim(),
      scheduledDate: submitted.date,
      slot: { start: newStart, end: newEnd },
      status: 'requested',
    })
  }

  return (
    <section>
      <h1>Schedule</h1>
      <ModelableGuide
        title="Scheduling joins identity to a daily projection"
        description="Appointments are generated from a versioned entity, while the schedule endpoint joins each appointment to its Patient and exposes a reporting-friendly daily shape."
        models={['scheduling.Appointment@1', 'reporting.DailySchedule@1', 'clinical.Encounter@1']}
        sourceHref="https://github.com/ktjn/modelable-showcase/blob/main/model/scheduling.mdl"
      />

      <form onSubmit={handleFilterSubmit}>
        <label>
          Date
          <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </label>
        <label>
          Filter by practitioner ID
          <input value={practitioner} onChange={(event) => setPractitioner(event.target.value)} />
        </label>
        <button type="submit">Load schedule</button>
      </form>

      <h2>New appointment</h2>
      <form onSubmit={handleCreateSubmit}>
        <label>
          Patient ID
          <input value={newPatientId} onChange={(event) => setNewPatientId(event.target.value)} />
        </label>
        <label>
          Practitioner ID
          <input value={newPractitionerId} onChange={(event) => setNewPractitionerId(event.target.value)} />
        </label>
        <label>
          Start
          <input type="time" step={1} value={newStart} onChange={(event) => setNewStart(event.target.value)} />
        </label>
        <label>
          End
          <input type="time" step={1} value={newEnd} onChange={(event) => setNewEnd(event.target.value)} />
        </label>
        <button type="submit" disabled={createMutation.isPending}>
          Book appointment
        </button>
        {createError && <p role="alert">{createError}</p>}
        {createMutation.isError && (
          <p role="alert">
            {createMutation.error instanceof Error ? createMutation.error.message : 'Failed to book appointment.'}
          </p>
        )}
      </form>

      <h2>Appointments on {submitted.date}</h2>
      {isLoading && <p>Loading schedule…</p>}
      {isError && <p role="alert">{error instanceof Error ? error.message : 'Failed to load schedule'}</p>}
      {data && data.length === 0 && <p>No appointments for this day.</p>}
      {data && data.length > 0 && (
        <ul>
          {data.map((appointment) => (
            <ScheduleRow
              key={appointment.appointmentId}
              appointment={appointment}
              encounter={encounters[appointment.appointmentId]}
              onEncounterStarted={(appointmentId, encounter) =>
                setEncounters((previous) => ({ ...previous, [appointmentId]: encounter }))
              }
              onEncounterUpdated={(appointmentId, encounter) =>
                setEncounters((previous) => ({ ...previous, [appointmentId]: encounter }))
              }
            />
          ))}
        </ul>
      )}
    </section>
  )
}
