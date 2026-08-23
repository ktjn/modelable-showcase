//! Deterministic in-memory application workflows for the clinic showcase.

use std::cmp::Reverse;
use std::collections::HashMap;

use billing_core::billing::billing_invoice_db_v2::BillingInvoiceDbV2Status;
use billing_core::billing::billing_invoice_reply_v2::BillingInvoiceReplyV2;
use billing_core::billing::billing_invoice_request_v2::BillingInvoiceRequestV2;
use billing_core::billing::billing_payment_received_v1::BillingPaymentReceivedV1;
use chrono::{DateTime, Duration, NaiveDate, Utc};
use clinic_core::patient::patient_id::PatientId;
use clinic_core::patient::patient_patient_reply_v2::PatientPatientReplyV2;
use clinic_core::patient::patient_patient_request_v2::PatientPatientRequestV2;
use clinic_core::scheduling::appointment_id::AppointmentId;
use clinic_core::scheduling::practitioner_id::PractitionerId;
use clinic_core::scheduling::scheduling_appointment_db_v1::SchedulingAppointmentDbV1Status;
use clinic_core::scheduling::scheduling_appointment_reply_v1::SchedulingAppointmentReplyV1;
use clinic_core::scheduling::scheduling_appointment_request_v1::SchedulingAppointmentRequestV1;
use clinic_core::scheduling::scheduling_time_range_v0::SchedulingTimeRangeV0;
use clinical_core::clinical::clinical_encounter_db_v1::ClinicalEncounterDbV1Status;
use clinical_core::clinical::clinical_encounter_reply_v1::ClinicalEncounterReplyV1;
use clinical_core::clinical::clinical_encounter_request_v1::ClinicalEncounterRequestV1;
use clinical_core::clinical::clinical_observation_v1::ClinicalObservationV1;
use clinical_core::clinical::encounter_id::EncounterId;
use serde::Serialize;

use crate::{billing, clinical, patient, scheduling, ClinicState, ShowcaseError};

#[derive(Debug, Clone, Default, PartialEq)]
pub struct AppointmentReschedule {
    pub scheduled_date: Option<NaiveDate>,
    pub slot: Option<SchedulingTimeRangeV0>,
    pub buffer_duration: Option<Duration>,
    pub reason: Option<String>,
    pub notes: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct EncounterUpdate {
    pub status: ClinicalEncounterDbV1Status,
    pub ended_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PatientSummary {
    pub patient_id: String,
    pub legal_name: String,
    pub preferred_name: Option<String>,
    pub date_of_birth: NaiveDate,
    pub preferred_language: String,
    pub appointment_count: i64,
    pub encounter_count: i64,
    pub observation_count: i64,
    pub invoice_count: i64,
    pub total_invoiced: Option<String>,
    pub total_paid: Option<String>,
    pub outstanding: Option<String>,
    pub last_encounter_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppointmentsPerDay {
    pub day: String,
    pub appointment_count: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PractitionerAppointmentCount {
    pub practitioner_id: String,
    pub appointment_count: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ClinicAnalytics {
    pub appointments_per_day: Vec<AppointmentsPerDay>,
    pub billed_total: String,
    pub paid_total: String,
    pub practitioner_appointment_counts: Vec<PractitionerAppointmentCount>,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct ClinicEngine {
    state: ClinicState,
}

impl ClinicEngine {
    pub fn from_state(state: ClinicState) -> Self {
        Self { state }
    }

    pub fn state(&self) -> &ClinicState {
        &self.state
    }

    pub fn into_state(self) -> ClinicState {
        self.state
    }

    pub(crate) fn replace_state(&mut self, state: ClinicState) {
        self.state = state;
    }

    pub fn create_patient(
        &mut self,
        request: &PatientPatientRequestV2,
        now: DateTime<Utc>,
    ) -> Result<PatientPatientReplyV2, ShowcaseError> {
        let id = request.patient_id;
        if self.state.patients.contains_key(&id) {
            return Err(already_exists("patient", id.to_string()));
        }
        let row = patient::request_to_db(request, now);
        self.state.patients.insert(id, row.clone());
        Ok(patient::db_to_reply(row))
    }

    pub fn get_patient(&self, id: PatientId) -> Result<PatientPatientReplyV2, ShowcaseError> {
        self.state
            .patients
            .get(&id)
            .cloned()
            .map(patient::db_to_reply)
            .ok_or_else(|| not_found("patient", id.to_string()))
    }

    pub fn search_patients(
        &self,
        name: Option<&str>,
        email: Option<&str>,
    ) -> Vec<PatientPatientReplyV2> {
        let name = normalized_filter(name);
        let email = normalized_filter(email);
        let mut rows: Vec<_> = self
            .state
            .patients
            .values()
            .filter(|row| {
                name.as_ref()
                    .is_none_or(|needle| row.legal_name.to_lowercase().contains(needle))
                    && email.as_ref().is_none_or(|needle| {
                        row.contact
                            .email
                            .as_ref()
                            .is_some_and(|value| value.to_lowercase().contains(needle))
                    })
            })
            .cloned()
            .collect();
        rows.sort_by_key(|row| (row.created_at, row.patient_id.to_string()));
        rows.into_iter().map(patient::db_to_reply).collect()
    }

    pub fn create_appointment(
        &mut self,
        request: &SchedulingAppointmentRequestV1,
        now: DateTime<Utc>,
    ) -> Result<SchedulingAppointmentReplyV1, ShowcaseError> {
        scheduling::validate_slot(&request.slot)?;
        let id = request.appointment_id;
        if self.state.appointments.contains_key(&id) {
            return Err(already_exists("appointment", id.to_string()));
        }
        if !self
            .state
            .patients
            .keys()
            .any(|patient_id| patient_id.to_string() == request.patient_id)
        {
            return Err(not_found("patient", request.patient_id.clone()));
        }
        self.ensure_no_overlap(
            request.practitioner_id,
            request.scheduled_date,
            &request.slot,
            None,
            "appointment overlaps an existing practitioner appointment",
        )?;

        let row = scheduling::request_to_db(request, now);
        self.state.appointments.insert(id, row.clone());
        Ok(scheduling::db_to_reply(row))
    }

    pub fn reschedule_appointment(
        &mut self,
        id: AppointmentId,
        update: AppointmentReschedule,
        now: DateTime<Utc>,
    ) -> Result<SchedulingAppointmentReplyV1, ShowcaseError> {
        let current = self
            .state
            .appointments
            .get(&id)
            .cloned()
            .ok_or_else(|| not_found("appointment", id.to_string()))?;
        if current.status == SchedulingAppointmentDbV1Status::Cancelled {
            return Err(conflict(
                "appointment",
                format!("appointment {} is cancelled", *id),
            ));
        }

        let scheduled_date = update.scheduled_date.unwrap_or(current.scheduled_date);
        let slot = update.slot.unwrap_or(current.slot);
        scheduling::validate_slot(&slot)?;
        self.ensure_no_overlap(
            current.practitioner_id,
            scheduled_date,
            &slot,
            Some(id),
            "reschedule overlaps an existing practitioner appointment",
        )?;

        let row = self
            .state
            .appointments
            .get_mut(&id)
            .expect("appointment remained present during synchronous update");
        row.scheduled_date = scheduled_date;
        row.slot = slot;
        if update.buffer_duration.is_some() {
            row.buffer_duration = update.buffer_duration;
        }
        if update.reason.is_some() {
            row.reason = update.reason;
        }
        if update.notes.is_some() {
            row.notes = update.notes;
        }
        row.updated_at = Some(now);
        Ok(scheduling::db_to_reply(row.clone()))
    }

    pub fn cancel_appointment(
        &mut self,
        id: AppointmentId,
        reason: Option<String>,
        now: DateTime<Utc>,
    ) -> Result<SchedulingAppointmentReplyV1, ShowcaseError> {
        let row = self
            .state
            .appointments
            .get_mut(&id)
            .ok_or_else(|| not_found("appointment", id.to_string()))?;
        if row.status == SchedulingAppointmentDbV1Status::Cancelled {
            return Err(conflict(
                "appointment",
                format!("appointment {} is already cancelled", *id),
            ));
        }
        row.status = SchedulingAppointmentDbV1Status::Cancelled;
        if reason.is_some() {
            row.reason = reason;
        }
        row.updated_at = Some(now);
        Ok(scheduling::db_to_reply(row.clone()))
    }

    pub fn daily_schedule(
        &self,
        date: NaiveDate,
        practitioner: Option<PractitionerId>,
    ) -> Vec<SchedulingAppointmentReplyV1> {
        let mut rows: Vec<_> = self
            .state
            .appointments
            .values()
            .filter(|row| {
                row.scheduled_date == date
                    && practitioner.is_none_or(|id| row.practitioner_id == id)
            })
            .cloned()
            .collect();
        rows.sort_by_key(|row| (row.slot.start, row.appointment_id.to_string()));
        rows.into_iter().map(scheduling::db_to_reply).collect()
    }

    pub fn patient_appointments(
        &self,
        patient_id: PatientId,
    ) -> Result<Vec<SchedulingAppointmentReplyV1>, ShowcaseError> {
        self.ensure_patient(patient_id)?;
        let id = patient_id.to_string();
        let mut rows: Vec<_> = self
            .state
            .appointments
            .values()
            .filter(|row| row.patient_id == id)
            .cloned()
            .collect();
        rows.sort_by_key(|row| {
            (
                row.scheduled_date,
                row.slot.start,
                row.appointment_id.to_string(),
            )
        });
        Ok(rows.into_iter().map(scheduling::db_to_reply).collect())
    }

    pub fn create_encounter(
        &mut self,
        request: &ClinicalEncounterRequestV1,
        now: DateTime<Utc>,
    ) -> Result<ClinicalEncounterReplyV1, ShowcaseError> {
        let id = request.encounter_id;
        if self.state.encounters.contains_key(&id) {
            return Err(already_exists("encounter", id.to_string()));
        }
        self.ensure_patient(request.patient_id)?;
        if let Some(appointment_id) = &request.appointment_id {
            let exists = self
                .state
                .appointments
                .keys()
                .any(|id| id.to_string() == *appointment_id);
            if !exists {
                return Err(not_found("appointment", appointment_id.clone()));
            }
        }
        let row = clinical::request_to_db(request, now);
        self.state.encounters.insert(id, row.clone());
        Ok(clinical::db_to_reply(row))
    }

    pub fn update_encounter(
        &mut self,
        id: EncounterId,
        update: EncounterUpdate,
        now: DateTime<Utc>,
    ) -> Result<ClinicalEncounterReplyV1, ShowcaseError> {
        let row = self
            .state
            .encounters
            .get_mut(&id)
            .ok_or_else(|| not_found("encounter", id.to_string()))?;
        if row.status == ClinicalEncounterDbV1Status::Cancelled {
            return Err(conflict(
                "encounter",
                format!("encounter {} is cancelled", *id),
            ));
        }
        let ended_at = match update.ended_at {
            Some(value) => Some(value),
            None if update.status == ClinicalEncounterDbV1Status::Completed => Some(now),
            None => row.ended_at,
        };
        row.status = update.status;
        row.ended_at = ended_at;
        row.updated_at = Some(now);
        Ok(clinical::db_to_reply(row.clone()))
    }

    pub fn record_observation(
        &mut self,
        observation: ClinicalObservationV1,
    ) -> Result<ClinicalObservationV1, ShowcaseError> {
        let encounter_exists = self
            .state
            .encounters
            .keys()
            .any(|id| id.to_string() == observation.encounter_id);
        if !encounter_exists {
            return Err(not_found("encounter", observation.encounter_id.clone()));
        }
        if self
            .state
            .observations
            .iter()
            .any(|existing| existing.observation_id == observation.observation_id)
        {
            return Err(already_exists(
                "observation",
                observation.observation_id.to_string(),
            ));
        }
        self.state.observations.push(observation.clone());
        Ok(observation)
    }

    pub fn observations(
        &self,
        encounter_id: EncounterId,
    ) -> Result<Vec<ClinicalObservationV1>, ShowcaseError> {
        if !self.state.encounters.contains_key(&encounter_id) {
            return Err(not_found("encounter", encounter_id.to_string()));
        }
        let id = encounter_id.to_string();
        let mut observations: Vec<_> = self
            .state
            .observations
            .iter()
            .filter(|observation| observation.encounter_id == id)
            .cloned()
            .collect();
        observations.sort_by_key(|observation| {
            (
                observation.recorded_at,
                observation.observation_id.to_string(),
            )
        });
        Ok(observations)
    }

    pub fn create_invoice(
        &mut self,
        request: &BillingInvoiceRequestV2,
        now: DateTime<Utc>,
    ) -> Result<BillingInvoiceReplyV2, ShowcaseError> {
        let id = request.invoice_id;
        if self.state.invoices.contains_key(&id) {
            return Err(already_exists("invoice", id.to_string()));
        }
        self.ensure_patient(request.patient_id)?;
        if let Some(encounter_id) = &request.encounter_id {
            let exists = self
                .state
                .encounters
                .keys()
                .any(|id| id.to_string() == *encounter_id);
            if !exists {
                return Err(not_found("encounter", encounter_id.clone()));
            }
        }
        billing::validate_invoice(request)?;
        let row = billing::request_to_db(request, now);
        self.state.invoices.insert(id, row.clone());
        Ok(billing::db_to_reply(row))
    }

    pub fn record_payment(
        &mut self,
        payment: BillingPaymentReceivedV1,
    ) -> Result<BillingPaymentReceivedV1, ShowcaseError> {
        if !self.state.invoices.contains_key(&payment.invoice_id) {
            return Err(not_found("invoice", payment.invoice_id.to_string()));
        }
        if self
            .state
            .payments
            .iter()
            .any(|existing| existing.payment_id == payment.payment_id)
        {
            return Err(already_exists("payment", payment.payment_id.to_string()));
        }
        billing::money_cents("payment amount", &payment.amount)?;
        self.state.payments.push(payment.clone());
        Ok(payment)
    }

    pub fn patient_summary(&self, patient_id: PatientId) -> Result<PatientSummary, ShowcaseError> {
        let patient = self
            .state
            .patients
            .get(&patient_id)
            .ok_or_else(|| not_found("patient", patient_id.to_string()))?;
        let patient_id_string = patient_id.to_string();
        let appointments: Vec<_> = self
            .state
            .appointments
            .values()
            .filter(|appointment| appointment.patient_id == patient_id_string)
            .collect();
        let encounters: Vec<_> = self
            .state
            .encounters
            .values()
            .filter(|encounter| encounter.patient_id == patient_id)
            .collect();
        let encounter_ids: Vec<_> = encounters
            .iter()
            .map(|encounter| encounter.encounter_id.to_string())
            .collect();
        let observations = self
            .state
            .observations
            .iter()
            .filter(|observation| encounter_ids.contains(&observation.encounter_id))
            .count();
        let invoices: Vec<_> = self
            .state
            .invoices
            .values()
            .filter(|invoice| invoice.patient_id == patient_id)
            .collect();
        let invoice_ids: Vec<_> = invoices.iter().map(|invoice| invoice.invoice_id).collect();
        let payments: Vec<_> = self
            .state
            .payments
            .iter()
            .filter(|payment| invoice_ids.contains(&payment.invoice_id))
            .collect();

        let total_invoiced = optional_money_sum(
            invoices
                .iter()
                .map(|invoice| ("invoice total", invoice.total.as_str())),
        )?;
        let total_paid = optional_money_sum(
            payments
                .iter()
                .map(|payment| ("payment amount", payment.amount.as_str())),
        )?;
        let outstanding_cents = money_sum(
            invoices
                .iter()
                .filter(|invoice| {
                    matches!(
                        invoice.status,
                        BillingInvoiceDbV2Status::Issued | BillingInvoiceDbV2Status::Overdue
                    )
                })
                .map(|invoice| ("invoice total", invoice.total.as_str())),
        )?;

        Ok(PatientSummary {
            patient_id: patient_id_string,
            legal_name: patient.legal_name.clone(),
            preferred_name: patient.preferred_name.clone(),
            date_of_birth: patient.date_of_birth,
            preferred_language: patient.preferred_language.clone(),
            appointment_count: appointments.len() as i64,
            encounter_count: encounters.len() as i64,
            observation_count: observations as i64,
            invoice_count: invoices.len() as i64,
            total_invoiced,
            total_paid,
            outstanding: Some(format_cents(outstanding_cents)),
            last_encounter_at: encounters
                .iter()
                .map(|encounter| encounter.started_at)
                .max(),
        })
    }

    pub fn analytics(&self) -> Result<ClinicAnalytics, ShowcaseError> {
        let mut days: HashMap<NaiveDate, u64> = HashMap::new();
        let mut practitioners: HashMap<PractitionerId, u64> = HashMap::new();
        for appointment in self.state.appointments.values() {
            *days.entry(appointment.scheduled_date).or_default() += 1;
            *practitioners
                .entry(appointment.practitioner_id)
                .or_default() += 1;
        }
        let mut appointments_per_day: Vec<_> = days
            .into_iter()
            .map(|(day, appointment_count)| AppointmentsPerDay {
                day: day.to_string(),
                appointment_count,
            })
            .collect();
        appointments_per_day.sort_by(|left, right| left.day.cmp(&right.day));

        let mut practitioner_appointment_counts: Vec<_> = practitioners
            .into_iter()
            .map(
                |(practitioner_id, appointment_count)| PractitionerAppointmentCount {
                    practitioner_id: practitioner_id.to_string(),
                    appointment_count,
                },
            )
            .collect();
        practitioner_appointment_counts.sort_by_key(|item| {
            (
                Reverse(item.appointment_count),
                item.practitioner_id.clone(),
            )
        });

        let billed_total = money_sum(
            self.state
                .invoices
                .values()
                .map(|invoice| ("invoice total", invoice.total.as_str())),
        )?;
        let paid_total = money_sum(
            self.state
                .payments
                .iter()
                .map(|payment| ("payment amount", payment.amount.as_str())),
        )?;

        Ok(ClinicAnalytics {
            appointments_per_day,
            billed_total: format_cents(billed_total),
            paid_total: format_cents(paid_total),
            practitioner_appointment_counts,
        })
    }

    fn ensure_patient(&self, id: PatientId) -> Result<(), ShowcaseError> {
        if self.state.patients.contains_key(&id) {
            Ok(())
        } else {
            Err(not_found("patient", id.to_string()))
        }
    }

    fn ensure_no_overlap(
        &self,
        practitioner_id: PractitionerId,
        date: NaiveDate,
        slot: &SchedulingTimeRangeV0,
        exclude: Option<AppointmentId>,
        message: &'static str,
    ) -> Result<(), ShowcaseError> {
        for appointment in self.state.appointments.values().filter(|appointment| {
            appointment.practitioner_id == practitioner_id
                && appointment.scheduled_date == date
                && appointment.status != SchedulingAppointmentDbV1Status::Cancelled
                && exclude != Some(appointment.appointment_id)
        }) {
            if scheduling::slots_overlap(&appointment.slot, slot)? {
                return Err(conflict("appointment", message));
            }
        }
        Ok(())
    }
}

fn normalized_filter(value: Option<&str>) -> Option<String> {
    value
        .filter(|value| !value.is_empty())
        .map(str::to_lowercase)
}

fn not_found(resource: &'static str, id: String) -> ShowcaseError {
    ShowcaseError::NotFound { resource, id }
}

fn conflict(resource: &'static str, message: impl Into<String>) -> ShowcaseError {
    ShowcaseError::Conflict {
        resource,
        message: message.into(),
    }
}

fn already_exists(resource: &'static str, id: String) -> ShowcaseError {
    conflict(resource, format!("{resource} {id} already exists"))
}

fn money_sum<'a>(
    values: impl IntoIterator<Item = (&'static str, &'a str)>,
) -> Result<i64, ShowcaseError> {
    values.into_iter().try_fold(0_i64, |total, (field, value)| {
        total
            .checked_add(billing::money_cents(field, value)?)
            .ok_or_else(|| ShowcaseError::InvalidMoney {
                field,
                value: value.to_string(),
            })
    })
}

fn optional_money_sum<'a>(
    values: impl IntoIterator<Item = (&'static str, &'a str)>,
) -> Result<Option<String>, ShowcaseError> {
    let values: Vec<_> = values.into_iter().collect();
    if values.is_empty() {
        return Ok(None);
    }
    money_sum(values).map(|total| Some(format_cents(total)))
}

fn format_cents(cents: i64) -> String {
    let sign = if cents < 0 { "-" } else { "" };
    let magnitude = cents.unsigned_abs();
    format!("{sign}{}.{:02}", magnitude / 100, magnitude % 100)
}

#[cfg(test)]
mod tests {
    use super::{AppointmentReschedule, ClinicEngine, EncounterUpdate};
    use crate::{ErrorCategory, ShowcaseError};
    use billing_core::billing::billing_invoice_request_v2::BillingInvoiceRequestV2;
    use billing_core::billing::billing_payment_received_v1::BillingPaymentReceivedV1;
    use billing_core::billing::invoice_id::InvoiceId;
    use chrono::{DateTime, NaiveDate, Utc};
    use clinic_core::patient::patient_id::PatientId;
    use clinic_core::patient::patient_patient_request_v2::PatientPatientRequestV2;
    use clinic_core::scheduling::scheduling_appointment_request_v1::SchedulingAppointmentRequestV1;
    use clinical_core::clinical::clinical_encounter_db_v1::ClinicalEncounterDbV1Status;
    use clinical_core::clinical::clinical_encounter_request_v1::ClinicalEncounterRequestV1;
    use clinical_core::clinical::clinical_observation_v1::ClinicalObservationV1;
    use clinical_core::clinical::encounter_id::EncounterId;
    use serde::de::DeserializeOwned;
    use serde_json::{json, Value};

    const PATIENT: &str = "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d";
    const APPOINTMENT: &str = "11111111-1111-1111-1111-111111111111";
    const ENCOUNTER: &str = "e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1";
    const PRACTITIONER: &str = "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1";
    const INVOICE: &str = "10101010-1010-1010-1010-101010101010";

    fn parse<T: DeserializeOwned>(value: Value) -> T {
        serde_json::from_value(value).expect("fixture matches generated type")
    }

    fn now(value: &str) -> DateTime<Utc> {
        DateTime::parse_from_rfc3339(value)
            .expect("fixture timestamp")
            .with_timezone(&Utc)
    }

    fn patient() -> PatientPatientRequestV2 {
        parse(json!({
            "patientId": PATIENT,
            "legalName": "Ada Lovelace",
            "preferredName": "Ada",
            "dateOfBirth": "1815-12-10",
            "contact": { "email": "ada@example.com", "phone": "555-0001" },
            "address": null,
            "preferredLanguage": "en",
            "alternatePhoneNumbers": null,
            "notes": null,
            "clinicalNotes": null
        }))
    }

    fn appointment(id: &str, start: &str, end: &str) -> SchedulingAppointmentRequestV1 {
        parse(json!({
            "appointmentId": id,
            "patientId": PATIENT,
            "practitionerId": PRACTITIONER,
            "scheduledDate": "2026-09-01",
            "slot": { "start": start, "end": end },
            "bufferDuration": null,
            "status": "confirmed",
            "reason": "Consultation",
            "notes": null
        }))
    }

    fn encounter() -> ClinicalEncounterRequestV1 {
        parse(json!({
            "encounterId": ENCOUNTER,
            "patientId": PATIENT,
            "practitionerId": PRACTITIONER,
            "appointmentId": APPOINTMENT,
            "status": "in_progress",
            "startedAt": "2026-09-01T09:00:00Z",
            "endedAt": null,
            "expectedDuration": null,
            "reasonCode": null,
            "diagnoses": null
        }))
    }

    fn observation() -> ClinicalObservationV1 {
        parse(json!({
            "observationId": "01010101-0101-0101-0101-010101010101",
            "encounterId": ENCOUNTER,
            "code": "temperature",
            "isAbnormal": false,
            "recordedAt": "2026-09-01T09:15:00Z",
            "temperatureCelsius": 36.8
        }))
    }

    fn invoice() -> BillingInvoiceRequestV2 {
        parse(json!({
            "invoiceId": INVOICE,
            "patientId": PATIENT,
            "encounterId": ENCOUNTER,
            "lines": [{
                "description": "Consultation",
                "quantity": 1,
                "unitPrice": "100.00",
                "lineTotal": "100.00"
            }],
            "subtotal": "100.00",
            "tax": "25.00",
            "total": "125.00",
            "currency": "SEK",
            "billingPeriod": "2026-09",
            "status": "issued",
            "issuedAt": "2026-09-01T10:00:00Z",
            "dueDate": "2026-10-01"
        }))
    }

    fn payment() -> BillingPaymentReceivedV1 {
        parse(json!({
            "paymentId": "02020202-0202-0202-0202-020202020202",
            "invoiceId": INVOICE,
            "amount": "75.00",
            "method": "card",
            "receivedAt": "2026-09-02T11:00:00Z"
        }))
    }

    #[test]
    fn complete_clinic_workflow_is_deterministic() {
        let created_at = now("2026-09-01T08:00:00Z");
        let updated_at = now("2026-09-01T09:30:00Z");
        let mut engine = ClinicEngine::default();

        let patient_reply = engine.create_patient(&patient(), created_at).unwrap();
        assert_eq!(patient_reply.legal_name, "Ada Lovelace");
        assert_eq!(
            engine.search_patients(Some("ada"), Some("EXAMPLE")).len(),
            1
        );
        assert_eq!(
            engine.get_patient(patient_reply.patient_id).unwrap(),
            patient_reply
        );
        assert_eq!(
            engine
                .create_patient(&patient(), created_at)
                .unwrap_err()
                .category(),
            ErrorCategory::Conflict
        );

        let appointment_reply = engine
            .create_appointment(
                &appointment(APPOINTMENT, "09:00:00", "09:30:00"),
                created_at,
            )
            .unwrap();
        let overlap = engine
            .create_appointment(
                &appointment(
                    "22222222-2222-2222-2222-222222222222",
                    "09:15:00",
                    "09:45:00",
                ),
                created_at,
            )
            .unwrap_err();
        assert_eq!(overlap.category(), ErrorCategory::Conflict);
        let adjacent = engine
            .create_appointment(
                &appointment(
                    "33333333-3333-3333-3333-333333333333",
                    "09:30:00",
                    "10:00:00",
                ),
                created_at,
            )
            .unwrap();
        engine
            .reschedule_appointment(
                adjacent.appointment_id,
                AppointmentReschedule {
                    scheduled_date: Some(NaiveDate::from_ymd_opt(2026, 9, 2).unwrap()),
                    ..AppointmentReschedule::default()
                },
                updated_at,
            )
            .unwrap();
        assert_eq!(
            engine
                .daily_schedule(NaiveDate::from_ymd_opt(2026, 9, 1).unwrap(), None)
                .len(),
            1
        );
        assert_eq!(
            engine
                .patient_appointments(patient_reply.patient_id)
                .unwrap()
                .len(),
            2
        );

        let encounter_reply = engine.create_encounter(&encounter(), created_at).unwrap();
        let encounter_id = encounter_reply.encounter_id;
        let completed = engine
            .update_encounter(
                encounter_id,
                EncounterUpdate {
                    status: ClinicalEncounterDbV1Status::Completed,
                    ended_at: None,
                },
                updated_at,
            )
            .unwrap();
        assert_eq!(completed.ended_at, Some(updated_at));

        let observation = observation();
        let recorded = engine.record_observation(observation.clone()).unwrap();
        assert_eq!(engine.observations(encounter_id).unwrap(), vec![recorded]);
        assert_eq!(
            engine
                .record_observation(observation)
                .unwrap_err()
                .category(),
            ErrorCategory::Conflict
        );

        let invoice_reply = engine.create_invoice(&invoice(), updated_at).unwrap();
        assert_eq!(invoice_reply.total, "125.00");
        let payment = payment();
        engine.record_payment(payment.clone()).unwrap();
        assert_eq!(
            engine.record_payment(payment).unwrap_err().category(),
            ErrorCategory::Conflict
        );

        let summary = engine.patient_summary(patient_reply.patient_id).unwrap();
        assert_eq!(summary.appointment_count, 2);
        assert_eq!(summary.encounter_count, 1);
        assert_eq!(summary.observation_count, 1);
        assert_eq!(summary.invoice_count, 1);
        assert_eq!(summary.total_invoiced.as_deref(), Some("125.00"));
        assert_eq!(summary.total_paid.as_deref(), Some("75.00"));
        assert_eq!(summary.outstanding.as_deref(), Some("125.00"));

        let analytics = engine.analytics().unwrap();
        assert_eq!(analytics.appointments_per_day.len(), 2);
        assert_eq!(analytics.appointments_per_day[0].appointment_count, 1);
        assert_eq!(analytics.billed_total, "125.00");
        assert_eq!(analytics.paid_total, "75.00");

        engine
            .cancel_appointment(
                appointment_reply.appointment_id,
                Some("Away".into()),
                updated_at,
            )
            .unwrap();
        assert!(matches!(
            engine.reschedule_appointment(
                appointment_reply.appointment_id,
                AppointmentReschedule::default(),
                updated_at
            ),
            Err(ShowcaseError::Conflict { .. })
        ));
        engine
            .create_appointment(
                &appointment(
                    "44444444-4444-4444-4444-444444444444",
                    "09:00:00",
                    "09:30:00",
                ),
                updated_at,
            )
            .unwrap();
    }

    #[test]
    fn cancelled_encounter_is_terminal() {
        let timestamp = now("2026-09-01T08:00:00Z");
        let mut engine = ClinicEngine::default();
        engine.create_patient(&patient(), timestamp).unwrap();
        engine
            .create_appointment(&appointment(APPOINTMENT, "09:00:00", "09:30:00"), timestamp)
            .unwrap();
        let encounter = engine.create_encounter(&encounter(), timestamp).unwrap();
        engine
            .update_encounter(
                encounter.encounter_id,
                EncounterUpdate {
                    status: ClinicalEncounterDbV1Status::Cancelled,
                    ended_at: None,
                },
                timestamp,
            )
            .unwrap();
        assert_eq!(
            engine
                .update_encounter(
                    encounter.encounter_id,
                    EncounterUpdate {
                        status: ClinicalEncounterDbV1Status::Completed,
                        ended_at: None,
                    },
                    timestamp,
                )
                .unwrap_err()
                .category(),
            ErrorCategory::Conflict
        );
    }

    #[test]
    fn invoice_arithmetic_is_validated() {
        let mut engine = ClinicEngine::default();
        let timestamp = now("2026-09-01T08:00:00Z");
        engine.create_patient(&patient(), timestamp).unwrap();
        engine
            .create_appointment(&appointment(APPOINTMENT, "09:00:00", "09:30:00"), timestamp)
            .unwrap();
        engine.create_encounter(&encounter(), timestamp).unwrap();

        let mut invalid = invoice();
        invalid.total = "124.99".into();
        assert!(matches!(
            engine.create_invoice(&invalid, timestamp),
            Err(ShowcaseError::InvoiceArithmetic { .. })
        ));
    }

    #[test]
    fn empty_analytics_are_zeroed() {
        let analytics = ClinicEngine::default().analytics().unwrap();
        assert!(analytics.appointments_per_day.is_empty());
        assert!(analytics.practitioner_appointment_counts.is_empty());
        assert_eq!(analytics.billed_total, "0.00");
        assert_eq!(analytics.paid_total, "0.00");
    }

    #[test]
    fn unknown_entities_report_not_found() {
        let engine = ClinicEngine::default();
        let id = parse::<PatientId>(json!(PATIENT));
        assert_eq!(
            engine.get_patient(id).unwrap_err().category(),
            ErrorCategory::NotFound
        );
        let encounter_id = parse::<EncounterId>(json!(ENCOUNTER));
        assert_eq!(
            engine.observations(encounter_id).unwrap_err().category(),
            ErrorCategory::NotFound
        );
        let invoice_id = parse::<InvoiceId>(json!(INVOICE));
        assert_eq!(invoice_id.to_string(), INVOICE);
    }
}
