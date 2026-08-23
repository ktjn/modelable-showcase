//! Versioned persistence for the browser-hosted clinic runtime.

use billing_core::billing::billing_invoice_db_v2::BillingInvoiceDbV2;
use billing_core::billing::billing_payment_received_v1::BillingPaymentReceivedV1;
use chrono::{DateTime, Utc};
use clinic_core::patient::patient_patient_db_v2::PatientPatientDbV2;
use clinic_core::scheduling::scheduling_appointment_db_v1::SchedulingAppointmentDbV1;
use clinical_core::clinical::clinical_encounter_db_v1::ClinicalEncounterDbV1;
use clinical_core::clinical::clinical_observation_v1::ClinicalObservationV1;
use serde::de::DeserializeOwned;

use crate::{ClinicEngine, ClinicState, ClinicStateCounts, EncounterUpdate, ShowcaseError};

/// Current browser snapshot envelope format.
pub const SNAPSHOT_FORMAT_VERSION: u32 = 1;

/// A versioned, self-describing clinic state snapshot.
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SnapshotEnvelope {
    pub format_version: u32,
    pub modelable_version: String,
    pub schema_identity: String,
    pub state: ClinicState,
}

/// Modelable compiler version pinned by this repository.
pub fn modelable_version() -> &'static str {
    include_str!("../../../.modelable-version").trim()
}

/// Identity of every generated record representation stored in [`ClinicState`].
///
/// The full generated content signatures are retained instead of hashing them
/// again, so a changed stored schema cannot be hidden by a second digest.
pub fn schema_identity() -> String {
    [
        schema_part(
            "patient.PatientDb",
            PatientPatientDbV2::SCHEMA_VERSION,
            &PatientPatientDbV2::SCHEMA_CONTENT_SIGNATURE,
        ),
        schema_part(
            "scheduling.AppointmentDb",
            SchedulingAppointmentDbV1::SCHEMA_VERSION,
            &SchedulingAppointmentDbV1::SCHEMA_CONTENT_SIGNATURE,
        ),
        schema_part(
            "clinical.EncounterDb",
            ClinicalEncounterDbV1::SCHEMA_VERSION,
            &ClinicalEncounterDbV1::SCHEMA_CONTENT_SIGNATURE,
        ),
        schema_part(
            "clinical.Observation",
            ClinicalObservationV1::SCHEMA_VERSION,
            &ClinicalObservationV1::SCHEMA_CONTENT_SIGNATURE,
        ),
        schema_part(
            "billing.InvoiceDb",
            BillingInvoiceDbV2::SCHEMA_VERSION,
            &BillingInvoiceDbV2::SCHEMA_CONTENT_SIGNATURE,
        ),
        schema_part(
            "billing.PaymentReceived",
            BillingPaymentReceivedV1::SCHEMA_VERSION,
            &BillingPaymentReceivedV1::SCHEMA_CONTENT_SIGNATURE,
        ),
    ]
    .join("|")
}

fn schema_part(name: &str, version: u32, signature: &[u8; 32]) -> String {
    let signature = signature
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect::<String>();
    format!("{name}.v{version}:{signature}")
}

impl ClinicEngine {
    /// Capture the current state with compatibility metadata.
    pub fn snapshot(&self) -> SnapshotEnvelope {
        SnapshotEnvelope {
            format_version: SNAPSHOT_FORMAT_VERSION,
            modelable_version: modelable_version().to_string(),
            schema_identity: schema_identity(),
            state: self.state().clone(),
        }
    }

    /// Serialize the current snapshot for browser persistence or export.
    pub fn snapshot_json(&self) -> Result<String, ShowcaseError> {
        serde_json::to_string(&self.snapshot()).map_err(|error| ShowcaseError::Internal {
            message: format!("could not serialize clinic snapshot: {error}"),
        })
    }

    /// Restore compatible state without mutating this engine on failure.
    pub fn restore(&mut self, snapshot: SnapshotEnvelope) -> Result<(), ShowcaseError> {
        validate_compatibility(&snapshot)?;
        self.replace_state(snapshot.state);
        Ok(())
    }

    /// Decode and restore a JSON snapshot without mutating this engine on failure.
    pub fn restore_json(&mut self, snapshot: &str) -> Result<(), ShowcaseError> {
        let snapshot =
            serde_json::from_str(snapshot).map_err(|error| ShowcaseError::CorruptSnapshot {
                message: error.to_string(),
            })?;
        self.restore(snapshot)
    }

    /// Clear every record from this runtime.
    pub fn reset(&mut self) -> ClinicStateCounts {
        self.replace_state(ClinicState::default());
        self.state().counts()
    }

    /// Replace the runtime with a deterministic, synthetic end-to-end dataset.
    pub fn seed(&mut self) -> Result<ClinicStateCounts, ShowcaseError> {
        let mut seeded = ClinicEngine::default();
        let created_at = timestamp("2026-09-01T08:00:00Z")?;
        let completed_at = timestamp("2026-09-01T09:30:00Z")?;

        seeded.create_patient(&fixture(PATIENT)?, created_at)?;
        seeded.create_appointment(&fixture(APPOINTMENT)?, created_at)?;
        let encounter = seeded.create_encounter(&fixture(ENCOUNTER)?, created_at)?;
        seeded.update_encounter(
            encounter.encounter_id,
            EncounterUpdate {
                status: clinical_core::clinical::clinical_encounter_db_v1::ClinicalEncounterDbV1Status::Completed,
                ended_at: Some(completed_at),
            },
            completed_at,
        )?;
        seeded.record_observation(fixture(OBSERVATION)?)?;
        seeded.create_invoice(&fixture(INVOICE)?, completed_at)?;
        seeded.record_payment(fixture(PAYMENT)?)?;

        let counts = seeded.state().counts();
        self.replace_state(seeded.into_state());
        Ok(counts)
    }
}

fn validate_compatibility(snapshot: &SnapshotEnvelope) -> Result<(), ShowcaseError> {
    if snapshot.format_version != SNAPSHOT_FORMAT_VERSION {
        return Err(ShowcaseError::IncompatibleSnapshot {
            reason: format!(
                "format version {} is not supported; expected {}",
                snapshot.format_version, SNAPSHOT_FORMAT_VERSION
            ),
        });
    }
    let expected_identity = schema_identity();
    if snapshot.schema_identity != expected_identity {
        return Err(ShowcaseError::IncompatibleSnapshot {
            reason: "stored schema identity does not match this runtime".into(),
        });
    }
    Ok(())
}

fn fixture<T: DeserializeOwned>(json: &str) -> Result<T, ShowcaseError> {
    serde_json::from_str(json).map_err(|error| ShowcaseError::Internal {
        message: format!("invalid built-in seed fixture: {error}"),
    })
}

fn timestamp(value: &str) -> Result<DateTime<Utc>, ShowcaseError> {
    DateTime::parse_from_rfc3339(value)
        .map(|value| value.with_timezone(&Utc))
        .map_err(|error| ShowcaseError::Internal {
            message: format!("invalid built-in seed timestamp: {error}"),
        })
}

const PATIENT: &str = r#"{
  "patientId":"9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d",
  "legalName":"Ada Lovelace",
  "preferredName":"Ada",
  "dateOfBirth":"1815-12-10",
  "contact":{"email":"ada@example.com","phone":"555-0001"},
  "address":null,
  "preferredLanguage":"en",
  "alternatePhoneNumbers":null,
  "notes":null,
  "clinicalNotes":null
}"#;

const APPOINTMENT: &str = r#"{
  "appointmentId":"11111111-1111-1111-1111-111111111111",
  "patientId":"9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d",
  "practitionerId":"a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1",
  "scheduledDate":"2026-09-01",
  "slot":{"start":"09:00:00","end":"09:30:00"},
  "bufferDuration":null,
  "status":"confirmed",
  "reason":"Consultation",
  "notes":null
}"#;

const ENCOUNTER: &str = r#"{
  "encounterId":"e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1",
  "patientId":"9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d",
  "practitionerId":"a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1",
  "appointmentId":"11111111-1111-1111-1111-111111111111",
  "status":"in_progress",
  "startedAt":"2026-09-01T09:00:00Z",
  "endedAt":null,
  "expectedDuration":null,
  "reasonCode":null,
  "diagnoses":null
}"#;

const OBSERVATION: &str = r#"{
  "observationId":"01010101-0101-0101-0101-010101010101",
  "encounterId":"e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1",
  "code":"temperature",
  "isAbnormal":false,
  "recordedAt":"2026-09-01T09:15:00Z",
  "temperatureCelsius":36.8
}"#;

const INVOICE: &str = r#"{
  "invoiceId":"10101010-1010-1010-1010-101010101010",
  "patientId":"9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d",
  "encounterId":"e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1",
  "lines":[{"description":"Consultation","quantity":1,"unitPrice":"100.00","lineTotal":"100.00"}],
  "subtotal":"100.00",
  "tax":"25.00",
  "total":"125.00",
  "currency":"SEK",
  "billingPeriod":"2026-09",
  "status":"issued",
  "issuedAt":"2026-09-01T10:00:00Z",
  "dueDate":"2026-10-01"
}"#;

const PAYMENT: &str = r#"{
  "paymentId":"02020202-0202-0202-0202-020202020202",
  "invoiceId":"10101010-1010-1010-1010-101010101010",
  "amount":"75.00",
  "method":"card",
  "receivedAt":"2026-09-02T11:00:00Z"
}"#;

#[cfg(test)]
mod tests {
    use super::{schema_identity, ClinicEngine, SNAPSHOT_FORMAT_VERSION};
    use crate::{ErrorCategory, ShowcaseError};
    use chrono::NaiveDate;
    use clinic_core::patient::patient_id::PatientId;
    use clinical_core::clinical::encounter_id::EncounterId;

    #[test]
    fn empty_state_round_trips() {
        let source = ClinicEngine::default();
        let json = source.snapshot_json().unwrap();
        let mut restored = ClinicEngine::default();

        restored.restore_json(&json).unwrap();

        assert_eq!(restored.state(), source.state());
    }

    #[test]
    fn seeded_state_round_trips_with_equal_queries() {
        let mut source = ClinicEngine::default();
        let counts = source.seed().unwrap();
        assert_eq!(counts.patients, 1);
        assert_eq!(counts.appointments, 1);
        assert_eq!(counts.encounters, 1);
        assert_eq!(counts.observations, 1);
        assert_eq!(counts.invoices, 1);
        assert_eq!(counts.payments, 1);

        let json = source.snapshot_json().unwrap();
        let mut restored = ClinicEngine::default();
        restored.restore_json(&json).unwrap();

        assert_eq!(restored.state(), source.state());
        assert_eq!(restored.analytics().unwrap(), source.analytics().unwrap());
        let patient_id: PatientId =
            serde_json::from_str("\"9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d\"").unwrap();
        let encounter_id: EncounterId =
            serde_json::from_str("\"e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1\"").unwrap();
        assert_eq!(
            restored.get_patient(patient_id).unwrap(),
            source.get_patient(patient_id).unwrap()
        );
        assert_eq!(
            restored.daily_schedule(NaiveDate::from_ymd_opt(2026, 9, 1).unwrap(), None),
            source.daily_schedule(NaiveDate::from_ymd_opt(2026, 9, 1).unwrap(), None)
        );
        assert_eq!(
            restored.patient_appointments(patient_id).unwrap(),
            source.patient_appointments(patient_id).unwrap()
        );
        assert_eq!(
            restored.observations(encounter_id).unwrap(),
            source.observations(encounter_id).unwrap()
        );
        assert_eq!(
            restored.patient_summary(patient_id).unwrap(),
            source.patient_summary(patient_id).unwrap()
        );
        assert_eq!(
            restored.search_patients(Some("ada"), None),
            source.search_patients(Some("ada"), None)
        );
    }

    #[test]
    fn seed_is_deterministic() {
        let mut first = ClinicEngine::default();
        let mut second = ClinicEngine::default();

        first.seed().unwrap();
        second.seed().unwrap();

        assert_eq!(first.state(), second.state());
    }

    #[test]
    fn reset_clears_seeded_state() {
        let mut engine = ClinicEngine::default();
        engine.seed().unwrap();

        assert_eq!(engine.reset(), Default::default());
        assert!(engine.state().is_empty());
    }

    #[test]
    fn incompatible_format_does_not_replace_current_state() {
        let mut engine = ClinicEngine::default();
        engine.seed().unwrap();
        let before = engine.state().clone();
        let mut snapshot = engine.snapshot();
        snapshot.format_version = SNAPSHOT_FORMAT_VERSION + 1;

        let error = engine.restore(snapshot).unwrap_err();

        assert_eq!(error.category(), ErrorCategory::Validation);
        assert!(matches!(error, ShowcaseError::IncompatibleSnapshot { .. }));
        assert_eq!(engine.state(), &before);
    }

    #[test]
    fn incompatible_schema_does_not_replace_current_state() {
        let mut engine = ClinicEngine::default();
        engine.seed().unwrap();
        let before = engine.state().clone();
        let mut snapshot = engine.snapshot();
        snapshot.schema_identity = format!("{}-changed", schema_identity());

        let error = engine.restore(snapshot).unwrap_err();

        assert_eq!(error.category(), ErrorCategory::Validation);
        assert_eq!(engine.state(), &before);
    }

    #[test]
    fn corrupt_json_does_not_replace_current_state() {
        let mut engine = ClinicEngine::default();
        engine.seed().unwrap();
        let before = engine.state().clone();

        let error = engine.restore_json("{not-json").unwrap_err();

        assert_eq!(error.category(), ErrorCategory::BadRequest);
        assert_eq!(engine.state(), &before);
    }
}
