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

export type PatientCreateInput = PatientRequest

export function createPatient(request: PatientCreateInput): Promise<PatientReply> {
  return post<PatientReply>('/api/patients', request)
}
