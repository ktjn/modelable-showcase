//! Task 9.6 integration tests: the running Axum API's actual request/reply
//! shapes for the Task 9.2-9.4 `POST` create endpoints, checked against the
//! generated `generated/openapi/openapi.json` document (produced by `make
//! generate`; skips (early-return) if it is missing). Scoped to
//! `createPatient`/`createAppointment`/`createEncounter`/`createInvoice`
//! only - the `api {}` operations actually declared in `model/*.mdl` (Task
//! 9.6). `GET /api/patients/:id/summary` and `GET /api/analytics/clinic`
//! have no generated projection to declare an operation against (see the
//! `api {}` comments in `model/*.mdl`), so they are intentionally excluded.
//!
//! UPSTREAM_FINDINGS.md #36: the OpenAPI document's `properties` keys are the
//! Modelable source camelCase spelling (`patientId`), but the generated Rust
//! types' `serde` wire format is snake_case (`patient_id`) with no rename
//! attribute, so the actual JSON bodies below use snake_case throughout. Each
//! assertion here converts the actual body's keys to camelCase before
//! comparing them against the OpenAPI schema, which is the one non-generic
//! step in this file - everything else is a direct contract check.

use std::collections::BTreeSet;
use std::fs;
use std::time::Duration;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use axum::Router;
use http_body_util::BodyExt;
use modelable_showcase_api::{app, AppState};
use serde_json::{json, Value};
use tower::ServiceExt;

const PATIENT: &str = "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d";
const PRACTITIONER: &str = "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1";
const APPOINTMENT: &str = "11111111-1111-1111-1111-111111111111";
const ENCOUNTER: &str = "e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1";
const INVOICE: &str = "10101010-1010-1010-1010-101010101010";

fn openapi_doc() -> Option<Value> {
    let path = format!("{}/../../generated/openapi/openapi.json", env!("CARGO_MANIFEST_DIR"));
    match fs::read_to_string(&path) {
        Ok(text) => Some(serde_json::from_str(&text).expect("generated/openapi/openapi.json is not valid JSON")),
        Err(_) => {
            eprintln!("SKIP: {path} missing; run 'make generate' first to exercise the OpenAPI contract tests");
            None
        }
    }
}

async fn db_lock() -> tokio::sync::MutexGuard<'static, ()> {
    static LOCK: tokio::sync::Mutex<()> = tokio::sync::Mutex::const_new(());
    LOCK.lock().await
}

async fn app_ready() -> Option<Router> {
    let state = AppState::default();
    let reachable = tokio::time::timeout(
        Duration::from_secs(4),
        sqlx::query_scalar::<_, i32>("SELECT 1").fetch_one(&state.pool),
    )
    .await
    .map(|result| result.is_ok())
    .unwrap_or(false);
    if !reachable {
        eprintln!(
            "SKIP: showcase PostgreSQL unreachable; run 'docker compose up -d' \
             to exercise the OpenAPI contract tests"
        );
        return None;
    }
    for table in ["patient_db", "appointment_db", "encounter_db", "invoice_db"] {
        sqlx::query(&format!("TRUNCATE TABLE {table}"))
            .execute(&state.pool)
            .await
            .unwrap_or_else(|err| panic!("failed to TRUNCATE {table}: {err}"));
    }
    Some(app(state))
}

async fn post_json(router: &mut Router, uri: &str, body: Value) -> (StatusCode, Value) {
    let request = Request::builder()
        .method("POST")
        .uri(uri)
        .header("content-type", "application/json")
        .body(Body::from(body.to_string()))
        .unwrap();
    let response = router.oneshot(request).await.unwrap();
    let status = response.status();
    let bytes = response.into_body().collect().await.unwrap().to_bytes();
    let json = serde_json::from_slice(&bytes)
        .unwrap_or_else(|_| Value::String(String::from_utf8_lossy(&bytes).into_owned()));
    (status, json)
}

/// UPSTREAM_FINDINGS.md #36: the API's wire format is snake_case; the
/// generated OpenAPI schema's `properties` keys are Modelable's source
/// camelCase. `snake_case_two_words` -> `snakeCaseTwoWords`.
fn to_camel_case(snake: &str) -> String {
    let mut out = String::with_capacity(snake.len());
    let mut upper_next = false;
    for ch in snake.chars() {
        if ch == '_' {
            upper_next = true;
        } else if upper_next {
            out.extend(ch.to_uppercase());
            upper_next = false;
        } else {
            out.push(ch);
        }
    }
    out
}

fn object_keys_as_camel_case(value: &Value) -> BTreeSet<String> {
    value
        .as_object()
        .expect("expected a JSON object")
        .keys()
        .map(|key| to_camel_case(key))
        .collect()
}

fn schema_for<'a>(doc: &'a Value, name: &str) -> &'a Value {
    &doc["components"]["schemas"][name]
}

fn schema_property_keys(schema: &Value) -> BTreeSet<String> {
    schema["properties"].as_object().expect("schema has no properties").keys().cloned().collect()
}

fn schema_required_keys(schema: &Value) -> BTreeSet<String> {
    schema["required"]
        .as_array()
        .map(|values| values.iter().map(|v| v.as_str().unwrap().to_string()).collect())
        .unwrap_or_default()
}

/// Asserts `response_body`'s (snake_case) keys, converted to camelCase,
/// exactly match the OpenAPI schema's declared `required` properties plus
/// any of its optional `properties` actually present in the response - i.e.
/// every key in the response is documented, and every required key is
/// present.
fn assert_conforms_to_schema(doc: &Value, schema_name: &str, response_body: &Value) {
    let schema = schema_for(doc, schema_name);
    let documented = schema_property_keys(schema);
    let required = schema_required_keys(schema);
    let actual = object_keys_as_camel_case(response_body);

    let undocumented: BTreeSet<_> = actual.difference(&documented).collect();
    assert!(undocumented.is_empty(), "{schema_name}: response has undocumented fields {undocumented:?}: {response_body}");

    let missing_required: BTreeSet<_> = required.difference(&actual).collect();
    assert!(
        missing_required.is_empty(),
        "{schema_name}: response is missing required fields {missing_required:?}: {response_body}"
    );
}

#[tokio::test]
async fn create_patient_conforms_to_generated_openapi_contract() {
    let Some(doc) = openapi_doc() else { return };
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let operation = &doc["paths"]["/api/patients"]["post"];
    assert_eq!(operation["operationId"], "createPatient");

    let body = json!({
        "patient_id": PATIENT,
        "legal_name": "Ada Lovelace",
        "preferred_name": null,
        "date_of_birth": "1815-12-10",
        "contact": { "email": "ada@example.com", "phone": "555-0001" },
        "address": null,
        "preferred_language": "en",
        "alternate_phone_numbers": null,
        "notes": null,
        "clinical_notes": null,
    });
    let (status, reply) = post_json(&mut router, "/api/patients", body).await;
    let expected_status: u16 = operation["responses"].as_object().unwrap().keys().next().unwrap().parse().unwrap();
    assert_eq!(status.as_u16(), expected_status, "{reply}");
    assert_conforms_to_schema(&doc, "patient.PatientReply.v2", &reply);
}

#[tokio::test]
async fn create_appointment_conforms_to_generated_openapi_contract() {
    let Some(doc) = openapi_doc() else { return };
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let operation = &doc["paths"]["/api/appointments"]["post"];
    assert_eq!(operation["operationId"], "createAppointment");

    let body = json!({
        "appointment_id": APPOINTMENT,
        "patient_id": PATIENT,
        "practitioner_id": PRACTITIONER,
        "scheduled_date": "2026-09-01",
        "slot": { "start": "09:00:00", "end": "09:30:00" },
        "buffer_duration": null,
        "status": "requested",
        "reason": null,
        "notes": null,
    });
    let (status, reply) = post_json(&mut router, "/api/appointments", body).await;
    assert_eq!(status, StatusCode::CREATED, "{reply}");
    assert_conforms_to_schema(&doc, "scheduling.AppointmentReply.v1", &reply);
}

#[tokio::test]
async fn create_encounter_conforms_to_generated_openapi_contract() {
    let Some(doc) = openapi_doc() else { return };
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let operation = &doc["paths"]["/api/encounters"]["post"];
    assert_eq!(operation["operationId"], "createEncounter");

    let body = json!({
        "encounter_id": ENCOUNTER,
        "patient_id": PATIENT,
        "practitioner_id": PRACTITIONER,
        "appointment_id": null,
        "status": "in_progress",
        "started_at": "2026-09-01T09:00:00Z",
        "ended_at": null,
        "expected_duration": null,
        "reason_code": null,
        "diagnoses": null,
    });
    let (status, reply) = post_json(&mut router, "/api/encounters", body).await;
    assert_eq!(status, StatusCode::CREATED, "{reply}");
    assert_conforms_to_schema(&doc, "clinical.EncounterReply.v1", &reply);
}

#[tokio::test]
async fn create_invoice_conforms_to_generated_openapi_contract() {
    let Some(doc) = openapi_doc() else { return };
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let operation = &doc["paths"]["/api/invoices"]["post"];
    assert_eq!(operation["operationId"], "createInvoice");

    let body = json!({
        "invoice_id": INVOICE,
        "patient_id": PATIENT,
        "encounter_id": null,
        "lines": [
            { "description": "Consultation", "quantity": 1, "unit_price": "100.00", "line_total": "100.00" }
        ],
        "subtotal": "100.00",
        "tax": "25.00",
        "total": "125.00",
        "currency": "SEK",
        "billing_period": "2026-09",
        "status": "issued",
        "issued_at": "2026-09-01T10:00:00Z",
        "due_date": "2026-10-01",
    });
    let (status, reply) = post_json(&mut router, "/api/invoices", body).await;
    assert_eq!(status, StatusCode::CREATED, "{reply}");
    assert_conforms_to_schema(&doc, "billing.InvoiceReply.v2", &reply);
}
