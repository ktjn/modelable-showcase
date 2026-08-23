//! Compact JSON transport over the platform-neutral showcase clinic engine.

use billing_core::billing::billing_invoice_request_v2::BillingInvoiceRequestV2;
use billing_core::billing::billing_payment_received_v1::BillingPaymentReceivedV1;
use chrono::{DateTime, NaiveDate, Utc};
use clinic_core::patient::patient_id::PatientId;
use clinic_core::patient::patient_patient_request_v2::PatientPatientRequestV2;
use clinic_core::scheduling::appointment_id::AppointmentId;
use clinic_core::scheduling::practitioner_id::PractitionerId;
use clinic_core::scheduling::scheduling_appointment_request_v1::SchedulingAppointmentRequestV1;
use clinical_core::clinical::clinical_encounter_request_v1::ClinicalEncounterRequestV1;
use clinical_core::clinical::clinical_observation_v1::ClinicalObservationV1;
use clinical_core::clinical::encounter_id::EncounterId;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use showcase_core::{
    modelable_version, schema_identity, AppointmentReschedule, ClinicEngine, ClinicStateCounts,
    EncounterUpdate, ErrorCategory, ShowcaseError, SNAPSHOT_FORMAT_VERSION,
};
use wasm_bindgen::prelude::*;

/// Stateful browser runtime exposed through one JSON-string ABI.
#[wasm_bindgen]
#[derive(Default)]
pub struct ShowcaseRuntime {
    engine: ClinicEngine,
}

#[wasm_bindgen]
impl ShowcaseRuntime {
    #[wasm_bindgen(constructor)]
    pub fn new() -> Self {
        Self::default()
    }

    /// Initialize empty state or restore one supplied snapshot.
    pub fn initialize(&mut self, snapshot_json: Option<String>) -> String {
        let result = match snapshot_json {
            Some(snapshot) => self.engine.restore_json(&snapshot),
            None => {
                self.engine.reset();
                Ok(())
            }
        };
        match result {
            Ok(()) => success(self.info()),
            Err(error) => failure(error),
        }
    }

    /// Execute one tagged mutating command.
    pub fn execute(&mut self, command_json: &str) -> String {
        let envelope: CommandEnvelope = match serde_json::from_str(command_json) {
            Ok(command) => command,
            Err(error) => return malformed("command", error),
        };
        let now = envelope.now;
        let result = match envelope.command {
            Command::CreatePatient(request) => value(self.engine.create_patient(&request, now)),
            Command::CreateAppointment(request) => {
                value(self.engine.create_appointment(&request, now))
            }
            Command::RescheduleAppointment(payload) => value(self.engine.reschedule_appointment(
                payload.appointment_id,
                payload.changes,
                now,
            )),
            Command::CancelAppointment(payload) => value(self.engine.cancel_appointment(
                payload.appointment_id,
                payload.reason,
                now,
            )),
            Command::CreateEncounter(request) => value(self.engine.create_encounter(&request, now)),
            Command::UpdateEncounter(payload) => value(self.engine.update_encounter(
                payload.encounter_id,
                payload.changes,
                now,
            )),
            Command::RecordObservation(observation) => {
                value(self.engine.record_observation(observation))
            }
            Command::CreateInvoice(request) => value(self.engine.create_invoice(&request, now)),
            Command::RecordPayment(payment) => value(self.engine.record_payment(payment)),
        };
        result.map(success).unwrap_or_else(failure)
    }

    /// Execute one tagged read-only query.
    pub fn query(&self, query_json: &str) -> String {
        let query: Query = match serde_json::from_str(query_json) {
            Ok(query) => query,
            Err(error) => return malformed("query", error),
        };
        let result = match query {
            Query::GetPatient(payload) => value(self.engine.get_patient(payload.patient_id)),
            Query::SearchPatients(payload) => Ok(json!(self
                .engine
                .search_patients(payload.name.as_deref(), payload.email.as_deref()))),
            Query::DailySchedule(payload) => Ok(json!(self
                .engine
                .daily_schedule(payload.date, payload.practitioner_id))),
            Query::PatientAppointments(payload) => {
                value(self.engine.patient_appointments(payload.patient_id))
            }
            Query::Observations(payload) => value(self.engine.observations(payload.encounter_id)),
            Query::PatientSummary(payload) => {
                value(self.engine.patient_summary(payload.patient_id))
            }
            Query::Analytics => value(self.engine.analytics()),
        };
        result.map(success).unwrap_or_else(failure)
    }

    /// Return a versioned snapshot envelope.
    pub fn snapshot(&self) -> String {
        success(self.engine.snapshot())
    }

    /// Clear all in-memory state and return runtime metadata.
    pub fn reset(&mut self) -> String {
        self.engine.reset();
        success(self.info())
    }

    /// Replace state with deterministic synthetic demo data.
    pub fn seed(&mut self) -> String {
        match self.engine.seed() {
            Ok(_) => success(self.info()),
            Err(error) => failure(error),
        }
    }
}

impl ShowcaseRuntime {
    fn info(&self) -> RuntimeInfo {
        RuntimeInfo {
            modelable_version: modelable_version().to_string(),
            schema_identity: schema_identity(),
            snapshot_format_version: SNAPSHOT_FORMAT_VERSION,
            counts: self.engine.state().counts(),
        }
    }
}

#[derive(Debug, Deserialize)]
struct CommandEnvelope {
    now: DateTime<Utc>,
    #[serde(flatten)]
    command: Command,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type", content = "payload")]
enum Command {
    CreatePatient(PatientPatientRequestV2),
    CreateAppointment(SchedulingAppointmentRequestV1),
    RescheduleAppointment(RescheduleAppointmentPayload),
    CancelAppointment(CancelAppointmentPayload),
    CreateEncounter(ClinicalEncounterRequestV1),
    UpdateEncounter(UpdateEncounterPayload),
    RecordObservation(ClinicalObservationV1),
    CreateInvoice(BillingInvoiceRequestV2),
    RecordPayment(BillingPaymentReceivedV1),
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RescheduleAppointmentPayload {
    appointment_id: AppointmentId,
    changes: AppointmentReschedule,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CancelAppointmentPayload {
    appointment_id: AppointmentId,
    reason: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct UpdateEncounterPayload {
    encounter_id: EncounterId,
    changes: EncounterUpdate,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type", content = "payload")]
enum Query {
    GetPatient(PatientIdPayload),
    SearchPatients(PatientSearch),
    DailySchedule(DailyScheduleQuery),
    PatientAppointments(PatientIdPayload),
    Observations(EncounterIdPayload),
    PatientSummary(PatientIdPayload),
    Analytics,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PatientIdPayload {
    patient_id: PatientId,
}

#[derive(Debug, Deserialize)]
struct PatientSearch {
    #[serde(default)]
    name: Option<String>,
    #[serde(default)]
    email: Option<String>,
}

#[derive(Debug, Deserialize)]
struct DailyScheduleQuery {
    date: NaiveDate,
    #[serde(default, rename = "practitionerId")]
    practitioner_id: Option<PractitionerId>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct EncounterIdPayload {
    encounter_id: EncounterId,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimeInfo {
    modelable_version: String,
    schema_identity: String,
    snapshot_format_version: u32,
    counts: ClinicStateCounts,
}

#[derive(Debug, Serialize)]
struct RuntimeError {
    category: ErrorCategory,
    message: String,
}

fn value<T: Serialize>(result: Result<T, ShowcaseError>) -> Result<Value, ShowcaseError> {
    result.and_then(|value| {
        serde_json::to_value(value).map_err(|error| ShowcaseError::Internal {
            message: format!("could not serialize runtime result: {error}"),
        })
    })
}

fn success<T: Serialize>(result: T) -> String {
    match serde_json::to_value(result) {
        Ok(result) => json!({ "ok": true, "result": result }).to_string(),
        Err(error) => failure(ShowcaseError::Internal {
            message: format!("could not serialize runtime response: {error}"),
        }),
    }
}

fn failure(error: ShowcaseError) -> String {
    json!({
        "ok": false,
        "error": RuntimeError {
            category: error.category(),
            message: error.to_string(),
        }
    })
    .to_string()
}

fn malformed(kind: &str, error: serde_json::Error) -> String {
    json!({
        "ok": false,
        "error": RuntimeError {
            category: ErrorCategory::BadRequest,
            message: format!("invalid {kind} JSON: {error}"),
        }
    })
    .to_string()
}

#[cfg(test)]
mod tests {
    use super::ShowcaseRuntime;
    use serde_json::{json, Value};

    fn response(json: &str) -> Value {
        serde_json::from_str(json).expect("runtime always returns JSON")
    }

    #[test]
    fn initialize_and_errors_use_stable_envelopes() {
        let mut runtime = ShowcaseRuntime::new();
        let initialized = response(&runtime.initialize(None));
        assert_eq!(initialized["ok"], true);
        assert_eq!(initialized["result"]["counts"]["patients"], 0);

        let malformed = response(&runtime.query("{not-json"));
        assert_eq!(malformed["ok"], false);
        assert_eq!(malformed["error"]["category"], "bad_request");

        let malformed_id = response(
            &runtime.query(r#"{"type":"GetPatient","payload":{"patientId":"not-a-uuid"}}"#),
        );
        assert_eq!(malformed_id["ok"], false);
        assert_eq!(malformed_id["error"]["category"], "bad_request");

        let incompatible = json!({
            "formatVersion": 999,
            "modelableVersion": "test",
            "schemaIdentity": "test",
            "state": {
                "patients": {},
                "appointments": {},
                "encounters": {},
                "observations": [],
                "invoices": {},
                "payments": []
            }
        });
        let incompatible = response(&runtime.initialize(Some(incompatible.to_string())));
        assert_eq!(incompatible["ok"], false);
        assert_eq!(incompatible["error"]["category"], "validation");
    }

    #[test]
    fn commands_queries_and_snapshots_share_one_json_boundary() {
        let mut runtime = ShowcaseRuntime::new();
        let create = json!({
            "type": "CreatePatient",
            "now": "2026-09-01T08:00:00Z",
            "payload": {
                "patientId": "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d",
                "legalName": "Ada Lovelace",
                "preferredName": "Ada",
                "dateOfBirth": "1815-12-10",
                "contact": { "email": "ada@example.com", "phone": "555-0001" },
                "address": null,
                "preferredLanguage": "en",
                "alternatePhoneNumbers": null,
                "notes": null,
                "clinicalNotes": null
            }
        });
        assert_eq!(response(&runtime.execute(&create.to_string()))["ok"], true);
        assert_eq!(
            response(&runtime.execute(&create.to_string()))["error"]["category"],
            "conflict"
        );

        let query = json!({
            "type": "GetPatient",
            "payload": { "patientId": "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d" }
        });
        let queried = response(&runtime.query(&query.to_string()));
        assert_eq!(queried["result"]["legalName"], "Ada Lovelace");

        let snapshot = response(&runtime.snapshot())["result"].clone();
        runtime.reset();
        assert_eq!(
            response(&runtime.query(&query.to_string()))["error"]["category"],
            "not_found"
        );
        assert_eq!(
            response(&runtime.initialize(Some(snapshot.to_string())))["ok"],
            true
        );
        assert_eq!(response(&runtime.query(&query.to_string()))["ok"], true);
    }

    #[test]
    fn seed_exposes_complete_demo_analytics() {
        let mut runtime = ShowcaseRuntime::new();
        let seeded = response(&runtime.seed());
        assert_eq!(seeded["result"]["counts"]["payments"], 1);

        let analytics = response(&runtime.query(r#"{"type":"Analytics"}"#));
        assert_eq!(analytics["result"]["billedTotal"], "125.00");
        assert_eq!(analytics["result"]["paidTotal"], "75.00");
    }
}
