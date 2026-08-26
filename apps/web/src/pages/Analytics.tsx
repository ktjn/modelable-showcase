import { useQuery } from '@tanstack/react-query'
import { getClinicAnalytics } from '../api/analytics'
import { ModelableGuide } from '../components/ModelableGuide'

export function Analytics() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['analytics', 'clinic'],
    queryFn: getClinicAnalytics,
  })

  return (
    <section>
      <h1>Analytics</h1>
      <ModelableGuide
        title="Reporting is where domains meet"
        description="The totals and breakdowns are computed from billing and scheduling events, mirroring the cross-domain aggregates defined in reporting.mdl."
        models={['reporting.MonthlyClinicStats@1', 'reporting.PractitionerRevenue@1', 'billing.PaymentReceived@1']}
        sourceHref="https://github.com/ktjn/modelable-showcase/blob/main/model/reporting.mdl"
      />

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
