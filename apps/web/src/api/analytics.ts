import { get } from './client'

// Hand-composed on the API side (apps/api/src/analytics.rs) from ClickHouse
// event tables - not a Modelable projection, so there is no generated type
// to import here (Task 9.5/9.6 note).
export interface AppointmentsPerDay {
  day: string
  appointmentCount: number
}

export interface PractitionerAppointmentCount {
  practitionerId: string
  appointmentCount: number
}

export interface ClinicAnalytics {
  appointmentsPerDay: AppointmentsPerDay[]
  billedTotal: string
  paidTotal: string
  practitionerAppointmentCounts: PractitionerAppointmentCount[]
}

export function getClinicAnalytics(): Promise<ClinicAnalytics> {
  return get<ClinicAnalytics>('/api/analytics/clinic')
}
