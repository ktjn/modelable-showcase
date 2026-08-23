//! Platform-neutral business behavior shared by the native API and the
//! browser-hosted WASM application.
//!
//! This crate deliberately contains no HTTP, async runtime, database, browser,
//! or storage dependencies. Generated Modelable contracts are its boundary
//! types; adapters remain responsible for transport and persistence.

use chrono::NaiveTime;
use std::fmt;

/// A semantic failure produced by deterministic showcase behavior.
///
/// Variants are added only when shared core behavior has a concrete consumer.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ShowcaseError {
    InvalidSlot { start: NaiveTime, end: NaiveTime },
}

impl fmt::Display for ShowcaseError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidSlot { start, end } => {
                write!(formatter, "slot end '{end}' is not after start '{start}'")
            }
        }
    }
}

impl std::error::Error for ShowcaseError {}

pub mod patient {
    use chrono::{DateTime, Utc};
    use clinic_core::patient::patient_patient_db_v2::PatientPatientDbV2;
    use clinic_core::patient::patient_patient_reply_v2::PatientPatientReplyV2;
    use clinic_core::patient::patient_patient_request_v2::PatientPatientRequestV2;

    pub fn request_to_db(
        request: &PatientPatientRequestV2,
        created_at: DateTime<Utc>,
    ) -> PatientPatientDbV2 {
        PatientPatientDbV2 {
            patient_id: request.patient_id,
            legal_name: request.legal_name.clone(),
            preferred_name: request.preferred_name.clone(),
            date_of_birth: request.date_of_birth,
            contact: request.contact.clone(),
            address: request.address.clone(),
            preferred_language: request.preferred_language.clone(),
            alternate_phone_numbers: request.alternate_phone_numbers.clone(),
            notes: request.notes.clone(),
            clinical_notes: request.clinical_notes.clone(),
            created_at,
            updated_at: None,
        }
    }

    pub fn db_to_reply(db: PatientPatientDbV2) -> PatientPatientReplyV2 {
        PatientPatientReplyV2 {
            patient_id: db.patient_id,
            legal_name: db.legal_name,
            preferred_name: db.preferred_name,
            date_of_birth: db.date_of_birth,
            contact: db.contact,
            address: db.address,
            preferred_language: db.preferred_language,
            alternate_phone_numbers: db.alternate_phone_numbers,
            notes: db.notes,
            clinical_notes: db.clinical_notes,
            created_at: db.created_at,
            updated_at: db.updated_at,
        }
    }
}

pub mod scheduling {
    use super::ShowcaseError;
    use chrono::{DateTime, Utc};
    use clinic_core::scheduling::scheduling_appointment_db_v1::{
        SchedulingAppointmentDbV1, SchedulingAppointmentDbV1Status,
    };
    use clinic_core::scheduling::scheduling_appointment_reply_v1::{
        SchedulingAppointmentReplyV1, SchedulingAppointmentReplyV1Status,
    };
    use clinic_core::scheduling::scheduling_appointment_request_v1::{
        SchedulingAppointmentRequestV1, SchedulingAppointmentRequestV1Status,
    };
    use clinic_core::scheduling::scheduling_time_range_v0::SchedulingTimeRangeV0;

    pub fn request_status_to_db(
        status: SchedulingAppointmentRequestV1Status,
    ) -> SchedulingAppointmentDbV1Status {
        match status {
            SchedulingAppointmentRequestV1Status::Requested => {
                SchedulingAppointmentDbV1Status::Requested
            }
            SchedulingAppointmentRequestV1Status::Confirmed => {
                SchedulingAppointmentDbV1Status::Confirmed
            }
            SchedulingAppointmentRequestV1Status::Cancelled => {
                SchedulingAppointmentDbV1Status::Cancelled
            }
            SchedulingAppointmentRequestV1Status::Completed => {
                SchedulingAppointmentDbV1Status::Completed
            }
            SchedulingAppointmentRequestV1Status::NoShow => SchedulingAppointmentDbV1Status::NoShow,
        }
    }

    pub fn db_status_to_reply(
        status: SchedulingAppointmentDbV1Status,
    ) -> SchedulingAppointmentReplyV1Status {
        match status {
            SchedulingAppointmentDbV1Status::Requested => {
                SchedulingAppointmentReplyV1Status::Requested
            }
            SchedulingAppointmentDbV1Status::Confirmed => {
                SchedulingAppointmentReplyV1Status::Confirmed
            }
            SchedulingAppointmentDbV1Status::Cancelled => {
                SchedulingAppointmentReplyV1Status::Cancelled
            }
            SchedulingAppointmentDbV1Status::Completed => {
                SchedulingAppointmentReplyV1Status::Completed
            }
            SchedulingAppointmentDbV1Status::NoShow => SchedulingAppointmentReplyV1Status::NoShow,
        }
    }

    pub fn db_status_name(status: &SchedulingAppointmentDbV1Status) -> &'static str {
        match status {
            SchedulingAppointmentDbV1Status::Requested => "requested",
            SchedulingAppointmentDbV1Status::Confirmed => "confirmed",
            SchedulingAppointmentDbV1Status::Cancelled => "cancelled",
            SchedulingAppointmentDbV1Status::Completed => "completed",
            SchedulingAppointmentDbV1Status::NoShow => "no_show",
        }
    }

    pub fn validate_slot(slot: &SchedulingTimeRangeV0) -> Result<(), ShowcaseError> {
        if slot.end <= slot.start {
            return Err(ShowcaseError::InvalidSlot {
                start: slot.start,
                end: slot.end,
            });
        }
        Ok(())
    }

    pub fn slots_overlap(
        first: &SchedulingTimeRangeV0,
        second: &SchedulingTimeRangeV0,
    ) -> Result<bool, ShowcaseError> {
        validate_slot(first)?;
        validate_slot(second)?;
        Ok(first.start < second.end && second.start < first.end)
    }

    pub fn request_to_db(
        request: &SchedulingAppointmentRequestV1,
        created_at: DateTime<Utc>,
    ) -> SchedulingAppointmentDbV1 {
        SchedulingAppointmentDbV1 {
            appointment_id: request.appointment_id,
            patient_id: request.patient_id.clone(),
            practitioner_id: request.practitioner_id,
            scheduled_date: request.scheduled_date,
            slot: request.slot.clone(),
            buffer_duration: request.buffer_duration,
            status: request_status_to_db(request.status.clone()),
            reason: request.reason.clone(),
            notes: request.notes.clone(),
            created_at,
            updated_at: None,
        }
    }

    pub fn db_to_reply(db: SchedulingAppointmentDbV1) -> SchedulingAppointmentReplyV1 {
        SchedulingAppointmentReplyV1 {
            appointment_id: db.appointment_id,
            patient_id: db.patient_id,
            practitioner_id: db.practitioner_id,
            scheduled_date: db.scheduled_date,
            slot: db.slot,
            status: db_status_to_reply(db.status),
            created_at: db.created_at,
            buffer_duration: db.buffer_duration,
            reason: db.reason,
            notes: db.notes,
            updated_at: db.updated_at,
        }
    }
}

pub mod clinical {
    use chrono::{DateTime, Utc};
    use clinical_core::clinical::clinical_encounter_db_v1::{
        ClinicalEncounterDbV1, ClinicalEncounterDbV1Status,
    };
    use clinical_core::clinical::clinical_encounter_reply_v1::{
        ClinicalEncounterReplyV1, ClinicalEncounterReplyV1Status,
    };
    use clinical_core::clinical::clinical_encounter_request_v1::{
        ClinicalEncounterRequestV1, ClinicalEncounterRequestV1Status,
    };

    pub fn request_status_to_db(
        status: ClinicalEncounterRequestV1Status,
    ) -> ClinicalEncounterDbV1Status {
        match status {
            ClinicalEncounterRequestV1Status::InProgress => ClinicalEncounterDbV1Status::InProgress,
            ClinicalEncounterRequestV1Status::Completed => ClinicalEncounterDbV1Status::Completed,
            ClinicalEncounterRequestV1Status::Cancelled => ClinicalEncounterDbV1Status::Cancelled,
        }
    }

    pub fn db_status_to_reply(
        status: ClinicalEncounterDbV1Status,
    ) -> ClinicalEncounterReplyV1Status {
        match status {
            ClinicalEncounterDbV1Status::InProgress => ClinicalEncounterReplyV1Status::InProgress,
            ClinicalEncounterDbV1Status::Completed => ClinicalEncounterReplyV1Status::Completed,
            ClinicalEncounterDbV1Status::Cancelled => ClinicalEncounterReplyV1Status::Cancelled,
        }
    }

    pub fn db_status_name(status: &ClinicalEncounterDbV1Status) -> &'static str {
        match status {
            ClinicalEncounterDbV1Status::InProgress => "in_progress",
            ClinicalEncounterDbV1Status::Completed => "completed",
            ClinicalEncounterDbV1Status::Cancelled => "cancelled",
        }
    }

    pub fn request_to_db(
        request: &ClinicalEncounterRequestV1,
        created_at: DateTime<Utc>,
    ) -> ClinicalEncounterDbV1 {
        ClinicalEncounterDbV1 {
            encounter_id: request.encounter_id,
            patient_id: request.patient_id.clone(),
            practitioner_id: request.practitioner_id,
            appointment_id: request.appointment_id.clone(),
            status: request_status_to_db(request.status.clone()),
            started_at: request.started_at,
            ended_at: request.ended_at,
            expected_duration: request.expected_duration,
            reason_code: request.reason_code.clone(),
            diagnoses: request.diagnoses.clone(),
            created_at,
            updated_at: None,
        }
    }

    pub fn db_to_reply(db: ClinicalEncounterDbV1) -> ClinicalEncounterReplyV1 {
        ClinicalEncounterReplyV1 {
            encounter_id: db.encounter_id,
            patient_id: db.patient_id,
            practitioner_id: db.practitioner_id,
            appointment_id: db.appointment_id,
            status: db_status_to_reply(db.status),
            started_at: db.started_at,
            ended_at: db.ended_at,
            expected_duration: db.expected_duration,
            reason_code: db.reason_code,
            diagnoses: db.diagnoses,
            created_at: db.created_at,
            updated_at: db.updated_at,
        }
    }
}

pub mod billing {
    use billing_core::billing::billing_invoice_db_v2::{
        BillingInvoiceDbV2, BillingInvoiceDbV2Status,
    };
    use billing_core::billing::billing_invoice_reply_v2::{
        BillingInvoiceReplyV2, BillingInvoiceReplyV2Status,
    };
    use billing_core::billing::billing_invoice_request_v2::{
        BillingInvoiceRequestV2, BillingInvoiceRequestV2Status,
    };
    use billing_core::billing::billing_payment_received_v1::BillingPaymentReceivedV1Method;
    use chrono::{DateTime, Utc};

    pub fn request_status_to_db(status: BillingInvoiceRequestV2Status) -> BillingInvoiceDbV2Status {
        match status {
            BillingInvoiceRequestV2Status::Draft => BillingInvoiceDbV2Status::Draft,
            BillingInvoiceRequestV2Status::Issued => BillingInvoiceDbV2Status::Issued,
            BillingInvoiceRequestV2Status::Paid => BillingInvoiceDbV2Status::Paid,
            BillingInvoiceRequestV2Status::Overdue => BillingInvoiceDbV2Status::Overdue,
            BillingInvoiceRequestV2Status::Void => BillingInvoiceDbV2Status::Void,
        }
    }

    pub fn db_status_to_reply(status: BillingInvoiceDbV2Status) -> BillingInvoiceReplyV2Status {
        match status {
            BillingInvoiceDbV2Status::Draft => BillingInvoiceReplyV2Status::Draft,
            BillingInvoiceDbV2Status::Issued => BillingInvoiceReplyV2Status::Issued,
            BillingInvoiceDbV2Status::Paid => BillingInvoiceReplyV2Status::Paid,
            BillingInvoiceDbV2Status::Overdue => BillingInvoiceReplyV2Status::Overdue,
            BillingInvoiceDbV2Status::Void => BillingInvoiceReplyV2Status::Void,
        }
    }

    pub fn db_status_name(status: &BillingInvoiceDbV2Status) -> &'static str {
        match status {
            BillingInvoiceDbV2Status::Draft => "draft",
            BillingInvoiceDbV2Status::Issued => "issued",
            BillingInvoiceDbV2Status::Paid => "paid",
            BillingInvoiceDbV2Status::Overdue => "overdue",
            BillingInvoiceDbV2Status::Void => "void",
        }
    }

    pub fn payment_method_name(method: &BillingPaymentReceivedV1Method) -> &'static str {
        match method {
            BillingPaymentReceivedV1Method::Card => "card",
            BillingPaymentReceivedV1Method::Cash => "cash",
            BillingPaymentReceivedV1Method::BankTransfer => "bank_transfer",
            BillingPaymentReceivedV1Method::Insurance => "insurance",
        }
    }

    pub fn request_to_db(
        request: &BillingInvoiceRequestV2,
        created_at: DateTime<Utc>,
    ) -> BillingInvoiceDbV2 {
        BillingInvoiceDbV2 {
            invoice_id: request.invoice_id,
            patient_id: request.patient_id.clone(),
            encounter_id: request.encounter_id.clone(),
            lines: request.lines.clone(),
            subtotal: request.subtotal.clone(),
            tax: request.tax.clone(),
            total: request.total.clone(),
            currency: request.currency.clone(),
            billing_period: request.billing_period.clone(),
            status: request_status_to_db(request.status.clone()),
            issued_at: request.issued_at,
            due_date: request.due_date,
            created_at,
            updated_at: None,
        }
    }

    pub fn db_to_reply(db: BillingInvoiceDbV2) -> BillingInvoiceReplyV2 {
        BillingInvoiceReplyV2 {
            invoice_id: db.invoice_id,
            patient_id: db.patient_id,
            encounter_id: db.encounter_id,
            lines: db.lines,
            subtotal: db.subtotal,
            tax: db.tax,
            total: db.total,
            currency: db.currency,
            billing_period: db.billing_period,
            status: db_status_to_reply(db.status),
            issued_at: db.issued_at,
            due_date: db.due_date,
            created_at: db.created_at,
            updated_at: db.updated_at,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{billing, clinical, scheduling, ShowcaseError};
    use billing_core::billing::billing_invoice_db_v2::BillingInvoiceDbV2Status;
    use billing_core::billing::billing_invoice_reply_v2::BillingInvoiceReplyV2Status;
    use billing_core::billing::billing_payment_received_v1::BillingPaymentReceivedV1Method;
    use chrono::NaiveTime;
    use clinic_core::scheduling::scheduling_appointment_db_v1::SchedulingAppointmentDbV1Status;
    use clinic_core::scheduling::scheduling_appointment_reply_v1::SchedulingAppointmentReplyV1Status;
    use clinic_core::scheduling::scheduling_time_range_v0::SchedulingTimeRangeV0;
    use clinical_core::clinical::clinical_encounter_db_v1::ClinicalEncounterDbV1Status;
    use clinical_core::clinical::clinical_encounter_reply_v1::ClinicalEncounterReplyV1Status;

    fn time(hour: u32, minute: u32) -> NaiveTime {
        NaiveTime::from_hms_opt(hour, minute, 0).expect("test time is valid")
    }

    fn slot(start: (u32, u32), end: (u32, u32)) -> SchedulingTimeRangeV0 {
        SchedulingTimeRangeV0 {
            start: time(start.0, start.1),
            end: time(end.0, end.1),
        }
    }

    #[test]
    fn slot_must_have_positive_duration() {
        let invalid = slot((10, 0), (9, 30));
        assert_eq!(
            scheduling::validate_slot(&invalid),
            Err(ShowcaseError::InvalidSlot {
                start: time(10, 0),
                end: time(9, 30),
            })
        );
    }

    #[test]
    fn adjacent_slots_do_not_overlap() {
        let first = slot((9, 0), (9, 30));
        let adjacent = slot((9, 30), (10, 0));
        let overlapping = slot((9, 15), (9, 45));

        assert_eq!(scheduling::slots_overlap(&first, &adjacent), Ok(false));
        assert_eq!(scheduling::slots_overlap(&first, &overlapping), Ok(true));
    }

    #[test]
    fn persistence_names_and_reply_statuses_are_stable() {
        assert_eq!(
            scheduling::db_status_to_reply(SchedulingAppointmentDbV1Status::NoShow),
            SchedulingAppointmentReplyV1Status::NoShow
        );
        assert_eq!(
            scheduling::db_status_name(&SchedulingAppointmentDbV1Status::NoShow),
            "no_show"
        );
        assert_eq!(
            clinical::db_status_to_reply(ClinicalEncounterDbV1Status::InProgress),
            ClinicalEncounterReplyV1Status::InProgress
        );
        assert_eq!(
            clinical::db_status_name(&ClinicalEncounterDbV1Status::InProgress),
            "in_progress"
        );
        assert_eq!(
            billing::db_status_to_reply(BillingInvoiceDbV2Status::Overdue),
            BillingInvoiceReplyV2Status::Overdue
        );
        assert_eq!(
            billing::db_status_name(&BillingInvoiceDbV2Status::Overdue),
            "overdue"
        );
        assert_eq!(
            billing::payment_method_name(&BillingPaymentReceivedV1Method::BankTransfer),
            "bank_transfer"
        );
    }
}
