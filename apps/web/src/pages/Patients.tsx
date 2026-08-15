import type { Address, ContactDetails } from '../generated-types'

// Placeholder data typed against the real Modelable-generated shapes -
// proves the generated types are load-bearing, not just imported and
// unused (see generated-types.ts for why these two types specifically).
const placeholderContact: ContactDetails = {
  email: 'front-desk@modelable-clinic.example',
  phone: '+1-555-0100',
}

const placeholderAddress: Address = {
  street: '1 Clinic Way',
  city: 'Springfield',
  postalCode: '00000',
  country: 'US',
}

export function Patients() {
  return (
    <section>
      <h1>Patients</h1>
      <p>Patient roster placeholder - populated once the API is available (Phase 9/10).</p>
      <dl>
        <dt>Sample contact</dt>
        <dd>
          {placeholderContact.email} / {placeholderContact.phone}
        </dd>
        <dt>Sample address</dt>
        <dd>
          {placeholderAddress.street}, {placeholderAddress.city} {placeholderAddress.postalCode},{' '}
          {placeholderAddress.country}
        </dd>
      </dl>
    </section>
  )
}
