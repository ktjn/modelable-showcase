import type { EncounterReply } from '@generated/clinical.EncounterReply.v1'
import type { EncounterRequest } from '@generated/clinical.EncounterRequest.v1'
import { patch, post } from './client'

// Modelable's TypeScript ref<> output still models `appointmentId` as the
// referenced object, while the API accepts its identifier on the wire.
export type EncounterStartInput = Omit<EncounterRequest, 'appointmentId' | 'status'> & { appointmentId?: string }

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
