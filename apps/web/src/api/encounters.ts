import type { EncounterReply } from '@generated/clinical.EncounterReply.v1'
import type { EncounterRequest } from '@generated/clinical.EncounterRequest.v1'
import { patch, post } from './client'

// UPSTREAM_FINDINGS.md #38/#40: see appointments.ts's AppointmentCreateInput
// - the same ref<> (here `appointmentId: ref<scheduling.Appointment@1>`) and
// optionality corrections apply to EncounterRequest.
export type EncounterStartInput = Omit<
  EncounterRequest,
  'appointmentId' | 'endedAt' | 'expectedDuration' | 'reasonCode' | 'diagnoses' | 'status'
> &
  Partial<{
    appointmentId: string
    endedAt: string
    expectedDuration: string
    reasonCode: string
    diagnoses: unknown[]
  }>

export function startEncounter(request: EncounterStartInput): Promise<EncounterReply> {
  return post<EncounterReply>('/api/encounters', { ...request, status: 'in_progress' })
}

export function updateEncounterStatus(
  id: string,
  status: 'completed' | 'cancelled',
  endedAt?: string,
): Promise<EncounterReply> {
  return patch<EncounterReply>(`/api/encounters/${encodeURIComponent(id)}`, { status, endedAt })
}

export interface ObservationInput {
  observationId?: string
  code: string
  temperatureCelsius?: number
  weightKg?: string
  bloodPressureSystolic?: number
  bloodPressureDiastolic?: number
  pulseBpm?: number
  isAbnormal?: boolean
  recordedAt?: string
}

export function addObservation(encounterId: string, observation: ObservationInput): Promise<unknown> {
  return post(`/api/encounters/${encodeURIComponent(encounterId)}/observations`, observation)
}
