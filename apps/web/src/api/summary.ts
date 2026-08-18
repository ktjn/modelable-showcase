import { get } from './client'

// Hand-composed on the API side (apps/api/src/summary.rs) - a real
// multi-domain SQL aggregation, not a Modelable projection, so there is no
// generated type to import here (Task 9.4/9.6 note).
export interface PatientSummary {
  patientId: string
  legalName: string
  preferredName: string | null
  dateOfBirth: string
  preferredLanguage: string
  appointmentCount: number
  encounterCount: number
  observationCount: number
  invoiceCount: number
  totalInvoiced: string | null
  totalPaid: string | null
  outstanding: string | null
  lastEncounterAt: string | null
}

export function getPatientSummary(patientId: string): Promise<PatientSummary> {
  return get<PatientSummary>(`/api/patients/${encodeURIComponent(patientId)}/summary`)
}
