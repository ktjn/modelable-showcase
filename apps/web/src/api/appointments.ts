import type { AppointmentReply } from '@generated/scheduling.AppointmentReply.v1'
import type { AppointmentRequest } from '@generated/scheduling.AppointmentRequest.v1'
import { get, patch, post } from './client'

export interface DailyScheduleParams {
  date: string
  practitioner?: string
}

export function getDailySchedule(params: DailyScheduleParams): Promise<AppointmentReply[]> {
  const query = new URLSearchParams({ date: params.date })
  if (params.practitioner) query.set('practitioner', params.practitioner)
  return get<AppointmentReply[]>(`/api/schedule?${query.toString()}`)
}

export function getPatientAppointments(patientId: string): Promise<AppointmentReply[]> {
  return get<AppointmentReply[]>(`/api/patients/${encodeURIComponent(patientId)}/appointments`)
}

// UPSTREAM_FINDINGS.md #38: a ref<Domain.Entity@N> field (here `patientId:
// ref<patient.Patient@2>`) resolves to the full referenced entity type in
// every generated target, not the plain identifier it actually carries on
// the wire (a bare `patientId: string` is what apps/api's request/reply
// bodies actually exchange). AppointmentCreateInput corrects that field back
// to a string and, per #40, restores the true optionality of
// bufferDuration/reason/notes.
export type AppointmentCreateInput = Omit<
  AppointmentRequest,
  'patientId' | 'bufferDuration' | 'reason' | 'notes'
> & { patientId: string } & Partial<Pick<AppointmentRequest, 'bufferDuration' | 'reason' | 'notes'>>

export function createAppointment(request: AppointmentCreateInput): Promise<AppointmentReply> {
  return post<AppointmentReply>('/api/appointments', request)
}

export interface RescheduleInput {
  scheduledDate?: string
  slot?: { start: string; end: string }
  bufferDuration?: string
  reason?: string
  notes?: string
}

export function rescheduleAppointment(id: string, input: RescheduleInput): Promise<AppointmentReply> {
  return patch<AppointmentReply>(`/api/appointments/${encodeURIComponent(id)}`, input)
}

export function cancelAppointment(id: string, reason?: string): Promise<AppointmentReply> {
  return post<AppointmentReply>(`/api/appointments/${encodeURIComponent(id)}/cancel`, { reason })
}
