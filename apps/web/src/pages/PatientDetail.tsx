import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { getPatient } from '../api/patients'

export function PatientDetail() {
  const { id } = useParams<{ id: string }>()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['patient', id],
    queryFn: () => getPatient(id as string),
    enabled: Boolean(id),
  })

  if (isLoading) {
    return <p>Loading patient…</p>
  }
  if (isError) {
    return <p role="alert">{error instanceof Error ? error.message : 'Failed to load patient'}</p>
  }
  if (!data) {
    return null
  }

  return (
    <section>
      <h1>{data.legalName}</h1>
      <dl>
        <dt>Patient ID</dt>
        <dd>{data.patientId}</dd>
        <dt>Preferred name</dt>
        <dd>{data.preferredName || '—'}</dd>
        <dt>Date of birth</dt>
        <dd>{data.dateOfBirth}</dd>
        <dt>Email</dt>
        <dd>{data.contact?.email ?? '—'}</dd>
        <dt>Phone</dt>
        <dd>{data.contact?.phone ?? '—'}</dd>
        <dt>Address</dt>
        <dd>
          {data.address
            ? `${data.address.street}, ${data.address.city} ${data.address.postalCode}, ${data.address.country}`
            : '—'}
        </dd>
        <dt>Preferred language</dt>
        <dd>{data.preferredLanguage}</dd>
      </dl>
    </section>
  )
}
