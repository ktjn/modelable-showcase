//! Task 9.4 integration test: the patient summary aggregation endpoint.
//! Skips (early-return) when the showcase DB is unreachable.

use std::time::Duration;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use axum::Router;
use http_body_util::BodyExt;
use modelable_showcase_api::{app, AppState};
use serde_json::Value;
use tower::ServiceExt;

const PATIENT: &str = "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d";
const ENCOUNTER: &str = "e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1";
const PRACTITIONER: &str = "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1";
const INVOICE: &str = "10101010-1010-1010-1010-101010101010";
const APPOINTMENT: &str = "11111111-1111-1111-1111-111111111111";

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
        eprintln!("SKIP: showcase PostgreSQL unreachable; run 'docker compose up -d'");
        return None;
    }
    for table in ["patient_db", "appointment_db", "encounter_db", "observation_db", "invoice_db", "payment_db"] {
        sqlx::query(&format!("TRUNCATE TABLE {table} CASCADE"))
            .execute(&state.pool)
            .await
            .expect(&format!("failed to TRUNCATE {table}"));
    }
    Some(app(state))
}

async fn call(app: &mut Router, request: Request<Body>) -> (StatusCode, Value) {
    let response = app.oneshot(request).await.unwrap();
    let status = response.status();
    let bytes = response.into_body().collect().await.unwrap().to_bytes();
    let body = serde_json::from_slice(&bytes)
        .unwrap_or_else(|_| Value::String(String::from_utf8_lossy(&bytes).into_owned()));
    (status, body)
}

async fn post_json(router: &mut Router, uri: &str, body: Value) -> (StatusCode, Value) {
    let request = Request::builder()
        .method("POST")
        .uri(uri)
        .header("content-type", "application/json")
        .body(Body::from(body.to_string()))
        .unwrap();
    call(router, request).await
}

async fn seed(router: &mut Router) {
    // Patient.
    let patient = serde_json::json!({
        "patientId": PATIENT,
        "legalName": "Ada Lovelace",
        "preferredName": null,
        "dateOfBirth": "1815-12-10",
        "contact": { "email": "ada@example.com", "phone": "555-0001" },
        "address": null,
        "preferredLanguage": "en",
        "alternatePhoneNumbers": null,
        "notes": null,
        "clinicalNotes": null,
    });
    assert_eq!(post_json(router, "/api/patients", patient).await.0, StatusCode::CREATED);

    // Appointment.
    let appointment = serde_json::json!({
        "appointmentId": APPOINTMENT,
        "patientId": PATIENT,
        "practitionerId": PRACTITIONER,
        "scheduledDate": "2026-09-01",
        "slot": { "start": "09:00:00", "end": "09:30:00" },
        "bufferDuration": null,
        "status": "completed",
        "reason": null,
        "notes": null,
    });
    assert_eq!(post_json(router, "/api/appointments", appointment).await.0, StatusCode::CREATED);

    // Encounter.
    let encounter = serde_json::json!({
        "encounterId": ENCOUNTER,
        "patientId": PATIENT,
        "practitionerId": PRACTITIONER,
        "appointmentId": null,
        "status": "completed",
        "startedAt": "2026-09-01T09:00:00Z",
        "endedAt": "2026-09-01T09:30:00Z",
        "expectedDuration": null,
        "reasonCode": null,
        "diagnoses": null,
    });
    assert_eq!(post_json(router, "/api/encounters", encounter).await.0, StatusCode::CREATED);

    // Observation.
    let observation = serde_json::json!({
        "observationId": "01010101-0101-0101-0101-010101010101",
        "code": "temperature",
        "temperatureCelsius": 36.8,
        "isAbnormal": false,
        "recordedAt": "2026-09-01T09:15:00Z",
    });
    let uri = format!("/api/encounters/{ENCOUNTER}/observations");
    assert_eq!(post_json(router, &uri, observation).await.0, StatusCode::CREATED);

    // Invoice.
    let invoice = serde_json::json!({
        "invoiceId": INVOICE,
        "patientId": PATIENT,
        "encounterId": ENCOUNTER,
        "lines": [
            { "description": "Consultation", "quantity": 1, "unitPrice": "100.00", "lineTotal": "100.00" }
        ],
        "subtotal": "100.00",
        "tax": "25.00",
        "total": "125.00",
        "currency": "SEK",
        "billingPeriod": "2026-09",
        "status": "issued",
        "issuedAt": "2026-09-01T10:00:00Z",
        "dueDate": "2026-10-01",
    });
    assert_eq!(post_json(router, "/api/invoices", invoice).await.0, StatusCode::CREATED);

    // Payment.
    let payment = serde_json::json!({
        "paymentId": "02020202-0202-0202-0202-020202020202",
        "amount": "125.00",
        "method": "card",
        "receivedAt": "2026-09-02T11:00:00Z",
    });
    let uri = format!("/api/invoices/{INVOICE}/payments");
    assert_eq!(post_json(router, &uri, payment).await.0, StatusCode::CREATED);
}

#[tokio::test]
async fn patient_summary_aggregates_multi_domain_state() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };
    seed(&mut router).await;

    let uri = format!("/api/patients/{PATIENT}/summary");
    let (status, body) = call(&mut router, Request::builder().uri(&uri).body(Body::empty()).unwrap()).await;
    assert_eq!(status, StatusCode::OK, "{body}");
    assert_eq!(body["patientId"], PATIENT);
    assert_eq!(body["legalName"], "Ada Lovelace");
    assert_eq!(body["appointmentCount"], 1);
    assert_eq!(body["encounterCount"], 1);
    assert_eq!(body["observationCount"], 1);
    assert_eq!(body["invoiceCount"], 1);
    assert_eq!(body["totalInvoiced"], "125.00");
    assert_eq!(body["totalPaid"], "125.00");
    assert_eq!(body["outstanding"], "125.00");
    assert!(body["lastEncounterAt"].is_string(), "{body}");
}

#[tokio::test]
async fn patient_summary_for_unknown_patient_returns_404() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let uri = "/api/patients/00000000-0000-0000-0000-000000000000/summary";
    let (status, body) = call(&mut router, Request::builder().uri(uri).body(Body::empty()).unwrap()).await;
    assert_eq!(status, StatusCode::NOT_FOUND, "{body}");
}
