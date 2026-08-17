import type { PatientReply } from '@generated/patient.PatientReply.v2'
import type { PatientRequest } from '@generated/patient.PatientRequest.v2'
import { get, post } from './client'

export interface PatientSearchParams {
  name?: string
  email?: string
}

export function searchPatients(params: PatientSearchParams): Promise<PatientReply[]> {
  const query = new URLSearchParams()
  if (params.name) query.set('name', params.name)
  if (params.email) query.set('email', params.email)
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return get<PatientReply[]>(`/api/patients${suffix}`)
}

export function getPatient(id: string): Promise<PatientReply> {
  return get<PatientReply>(`/api/patients/${encodeURIComponent(id)}`)
}

// UPSTREAM_FINDINGS.md #37: the generated PatientRequest type marks every
// field required, including genuinely optional ones (preferredName,
// address, notes, clinicalNotes, alternatePhoneNumbers). This type
// re-declares the true optionality so the create form can omit them and
// still satisfy the compiler; the JSON wire format already omits an
// `undefined` field via `JSON.stringify`, so this is a type-only fix.
export type PatientCreateInput = Omit<
  PatientRequest,
  'preferredName' | 'address' | 'notes' | 'clinicalNotes' | 'alternatePhoneNumbers'
> &
  Partial<Pick<PatientRequest, 'preferredName' | 'address' | 'notes' | 'clinicalNotes' | 'alternatePhoneNumbers'>>

export function createPatient(request: PatientCreateInput): Promise<PatientReply> {
  return post<PatientReply>('/api/patients', request)
}
