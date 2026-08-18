import { useQuery } from '@tanstack/react-query'
import { getClinicAnalytics } from '../api/analytics'

export function Analytics() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['analytics', 'clinic'],
    queryFn: getClinicAnalytics,
  })

  return (
    <section>
      <h1>Analytics</h1>

      {isLoading && <p>Loading analytics…</p>}
      {isError && <p role="alert">{error instanceof Error ? error.message : 'Failed to load analytics'}</p>}

      {data && (
        <>
          <dl>
            <dt>Billed total</dt>
            <dd>{data.billedTotal}</dd>
            <dt>Paid total</dt>
            <dd>{data.paidTotal}</dd>
          </dl>

          <h2>Appointments per day</h2>
          {data.appointmentsPerDay.length === 0 ? (
            <p>No appointment activity yet.</p>
          ) : (
            <ul>
              {data.appointmentsPerDay.map((row) => (
                <li key={row.day}>
                  {row.day}: {row.appointmentCount}
                </li>
              ))}
            </ul>
          )}

          <h2>Appointments by practitioner</h2>
          {data.practitionerAppointmentCounts.length === 0 ? (
            <p>No appointment activity yet.</p>
          ) : (
            <ul>
              {data.practitionerAppointmentCounts.map((row) => (
                <li key={row.practitionerId}>
                  {row.practitionerId}: {row.appointmentCount}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}
