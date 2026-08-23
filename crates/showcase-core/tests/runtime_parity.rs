use std::collections::BTreeMap;

use billing_core::billing::billing_invoice_request_v2::BillingInvoiceRequestV2;
use billing_core::billing::billing_payment_received_v1::BillingPaymentReceivedV1;
use chrono::{DateTime, Utc};
use clinic_core::patient::patient_id::PatientId;
use clinic_core::patient::patient_patient_request_v2::PatientPatientRequestV2;
use clinic_core::scheduling::scheduling_appointment_request_v1::SchedulingAppointmentRequestV1;
use clinical_core::clinical::clinical_encounter_request_v1::ClinicalEncounterRequestV1;
use clinical_core::clinical::clinical_observation_v1::ClinicalObservationV1;
use clinical_core::clinical::encounter_id::EncounterId;
use serde::de::DeserializeOwned;
use serde::Deserialize;
use serde_json::Value;
use showcase_core::{ClinicEngine, EncounterUpdate, ErrorCategory, ShowcaseError};

const VECTORS: &str = include_str!("../../../tests/parity/runtime-parity.json");

#[derive(Debug, Deserialize)]
struct VectorSuite {
    version: u32,
    scenarios: Vec<Scenario>,
}

#[derive(Debug, Deserialize)]
struct Scenario {
    name: String,
    now: DateTime<Utc>,
    steps: Vec<Step>,
}

#[derive(Debug, Deserialize)]
struct Step {
    name: String,
    method: String,
    path: String,
    #[serde(default)]
    body: Option<Value>,
    expect: Expectation,
}

#[derive(Debug, Deserialize)]
struct Expectation {
    category: String,
    fields: BTreeMap<String, Value>,
}

struct Outcome {
    category: String,
    body: Option<Value>,
}

#[test]
fn application_vectors_match_the_direct_clinic_engine() {
    let suite: VectorSuite =
        serde_json::from_str(VECTORS).expect("parity vectors must be valid JSON");
    assert_eq!(suite.version, 1, "unsupported parity vector version");

    for scenario in suite.scenarios {
        let mut engine = ClinicEngine::default();
        for step in scenario.steps {
            let outcome = run(&mut engine, &step, scenario.now);
            assert_outcome(&scenario.name, &step, outcome);
        }
    }
}

fn run(engine: &mut ClinicEngine, step: &Step, now: DateTime<Utc>) -> Outcome {
    match (step.method.as_str(), step.path.as_str()) {
        ("POST", "/api/patients") => {
            outcome(engine.create_patient(&body::<PatientPatientRequestV2>(step), now))
        }
        ("POST", "/api/appointments") => {
            outcome(engine.create_appointment(&body::<SchedulingAppointmentRequestV1>(step), now))
        }
        ("POST", "/api/encounters") => {
            outcome(engine.create_encounter(&body::<ClinicalEncounterRequestV1>(step), now))
        }
        ("POST", "/api/invoices") => {
            outcome(engine.create_invoice(&body::<BillingInvoiceRequestV2>(step), now))
        }
        ("GET", "/api/analytics/clinic") => outcome(engine.analytics()),
        ("POST", path) if path.ends_with("/observations") => {
            let id = route_id(path, "/api/encounters/", "/observations");
            let mut payload = step.body.clone().expect("observation body");
            payload["encounterId"] = Value::String(id.to_owned());
            outcome(engine.record_observation(parse::<ClinicalObservationV1>(payload)))
        }
        ("PATCH", path) if path.starts_with("/api/encounters/") => {
            let id: EncounterId = parse(Value::String(
                path.trim_start_matches("/api/encounters/").to_owned(),
            ));
            outcome(engine.update_encounter(id, body::<EncounterUpdate>(step), now))
        }
        ("POST", path) if path.ends_with("/payments") => {
            let id = route_id(path, "/api/invoices/", "/payments");
            let mut payload = step.body.clone().expect("payment body");
            payload["invoiceId"] = Value::String(id.to_owned());
            outcome(engine.record_payment(parse::<BillingPaymentReceivedV1>(payload)))
        }
        ("GET", path) if path.ends_with("/summary") => {
            let id: PatientId = parse(Value::String(
                route_id(path, "/api/patients/", "/summary").to_owned(),
            ));
            outcome(engine.patient_summary(id))
        }
        _ => panic!("unsupported parity operation {} {}", step.method, step.path),
    }
}

fn body<T: DeserializeOwned>(step: &Step) -> T {
    parse(step.body.clone().expect("operation body"))
}

fn parse<T: DeserializeOwned>(value: Value) -> T {
    serde_json::from_value(value).expect("vector body must match its generated contract")
}

fn route_id<'a>(path: &'a str, prefix: &str, suffix: &str) -> &'a str {
    path.strip_prefix(prefix)
        .and_then(|value| value.strip_suffix(suffix))
        .expect("vector route must contain an identifier")
}

fn outcome<T: serde::Serialize>(result: Result<T, ShowcaseError>) -> Outcome {
    match result {
        Ok(value) => Outcome {
            category: "ok".to_owned(),
            body: Some(serde_json::to_value(value).expect("result must serialize")),
        },
        Err(error) => Outcome {
            category: category_name(error.category()),
            body: None,
        },
    }
}

fn category_name(category: ErrorCategory) -> String {
    serde_json::to_value(category)
        .expect("error category must serialize")
        .as_str()
        .expect("error category must be a string")
        .to_owned()
}

fn assert_outcome(scenario: &str, step: &Step, outcome: Outcome) {
    assert_eq!(
        outcome.category, step.expect.category,
        "scenario '{scenario}', step '{}' category",
        step.name
    );
    if step.expect.category != "ok" {
        return;
    }
    let body = outcome.body.expect("successful outcome body");
    for (pointer, expected) in &step.expect.fields {
        assert_eq!(
            body.pointer(pointer),
            Some(expected),
            "scenario '{scenario}', step '{}', field '{pointer}', body {body}",
            step.name
        );
    }
}
