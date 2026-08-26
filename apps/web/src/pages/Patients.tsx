import { useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import { searchPatients, type PatientSearchParams } from '../api/patients'
import { ModelableGuide } from '../components/ModelableGuide'

export function Patients() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState<PatientSearchParams>({})

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['patients', submitted],
    queryFn: () => searchPatients(submitted),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitted({ name: name.trim() || undefined, email: email.trim() || undefined })
  }

  return (
    <section>
      <h1>Patients</h1>
      <ModelableGuide
        title="Patient identity is a versioned entity"
        description="Search and create requests use the generated Patient@2 shape, including its semantic PatientId, contact value, and access annotations."
        models={['patient.Patient@2', 'patient.PatientRequest@2', 'patient.PatientReply@2']}
        sourceHref="https://github.com/ktjn/modelable-showcase/blob/main/model/patient.mdl"
      />
      <p>
        <Link to="/patients/new">New patient</Link>
      </p>

      <form onSubmit={handleSubmit}>
        <label>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Legal name" />
        </label>
        <label>
          Email
          <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" />
        </label>
        <button type="submit">Search</button>
      </form>

      {isLoading && <p>Loading patients…</p>}
      {isError && <p role="alert">{error instanceof Error ? error.message : 'Failed to load patients'}</p>}
      {data && data.length === 0 && <p>No patients found.</p>}
      {data && data.length > 0 && (
        <ul>
          {data.map((patient) => (
            <li key={patient.patientId}>
              <Link to={`/patients/${patient.patientId}`}>{patient.legalName}</Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
