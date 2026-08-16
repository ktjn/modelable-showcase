import type { PatientPatientV2 } from '@generated/patient.Patient.v2'

// Placeholder data typed against the real Modelable-generated Patient
// entity shape (UPSTREAM_FINDINGS.md #12/#13 are fixed in 1.8.0, so the
// entity interface - with its semantic-typed patientId and value-typed
// contact/address - is importable directly from generated/typescript).
const placeholderPatient: PatientPatientV2 = {
  patientId: '9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d',
  legalName: 'Ada Lovelace',
  preferredName: 'Ada',
  dateOfBirth: '1985-06-15',
  contact: {
    email: 'front-desk@modelable-clinic.example',
    phone: '+1-555-0100',
  },
  address: {
    street: '1 Clinic Way',
    city: 'Springfield',
    postalCode: '00000',
    country: 'US',
  },
  preferredLanguage: 'en',
  alternatePhoneNumbers: [],
  notes: 'Initial consultation',
  clinicalNotes: 'n/a',
  createdAt: '2026-08-16T00:00:00Z',
}

export function Patients() {
  return (
    <section>
      <h1>Patients</h1>
      <p>Patient roster placeholder - populated once the API is available (Phase 9/10).</p>
      <dl>
        <dt>Sample patient</dt>
        <dd>{placeholderPatient.legalName}</dd>
        <dt>Sample contact</dt>
        <dd>
          {placeholderPatient.contact.email} / {placeholderPatient.contact.phone}
        </dd>
        <dt>Sample address</dt>
        <dd>
          {placeholderPatient.address?.street}, {placeholderPatient.address?.city}{' '}
          {placeholderPatient.address?.postalCode}, {placeholderPatient.address?.country}
        </dd>
      </dl>
    </section>
  )
}
