import { useParams } from 'react-router-dom'

export function PatientDetail() {
  const { id } = useParams<{ id: string }>()
  return (
    <section>
      <h1>Patient {id}</h1>
      <p>Detail placeholder - populated once the API is available (Phase 9/10).</p>
    </section>
  )
}
