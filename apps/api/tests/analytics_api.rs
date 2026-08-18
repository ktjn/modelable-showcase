//! Task 9.5 integration test: the ClickHouse-backed analytics endpoint.
//! Skips (early-return) when the showcase PostgreSQL/ClickHouse are
//! unreachable; run `docker compose up -d` to execute it for real.

use std::time::Duration;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use axum::Router;
use http_body_util::BodyExt;
use modelable_showcase_api::{app, AppState};
use serde_json::Value;
use tower::ServiceExt;

const PATIENT: &str = "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d";
const PRACTITIONER: &str = "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1";
const INVOICE: &str = "10101010-1010-1010-1010-101010101010";
const APPOINTMENT: &str = "11111111-1111-1111-1111-111111111111";

async fn db_lock() -> tokio::sync::MutexGuard<'static, ()> {
    static LOCK: tokio::sync::Mutex<()> = tokio::sync::Mutex::const_new(());
    LOCK.lock().await
}

async fn app_ready() -> Option<Router> {
    let state = AppState::default();
    let pg_reachable = tokio::time::timeout(
        Duration::from_secs(4),
        sqlx::query_scalar::<_, i32>("SELECT 1").fetch_one(&state.pool),
    )
    .await
    .map(|result| result.is_ok())
    .unwrap_or(false);
    let ch_reachable = tokio::time::timeout(Duration::from_secs(4), state.clickhouse.query("SELECT 1").execute())
        .await
        .map(|result| result.is_ok())
        .unwrap_or(false);
    if !(pg_reachable && ch_reachable) {
        eprintln!(
            "SKIP: showcase PostgreSQL/ClickHouse unreachable; run 'docker compose up -d' \
             to exercise the analytics API integration test"
        );
        return None;
    }
    for table in ["patient_db", "appointment_db", "invoice_db", "payment_db"] {
        sqlx::query(&format!("TRUNCATE TABLE {table}"))
            .execute(&state.pool)
            .await
            .unwrap_or_else(|err| panic!("failed to TRUNCATE {table}: {err}"));
    }
    for table in ["appointment_event", "invoice_event", "payment_event"] {
        state
            .clickhouse
            .query(&format!("TRUNCATE TABLE {table}"))
            .execute()
            .await
            .unwrap_or_else(|err| panic!("failed to TRUNCATE {table}: {err}"));
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

async fn get(router: &mut Router, uri: &str) -> (StatusCode, Value) {
    call(router, Request::builder().uri(uri).body(Body::empty()).unwrap()).await
}

async fn seed(router: &mut Router) {
    let patient = serde_json::json!({
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
    assert_eq!(post_json(router, "/api/patients", patient).await.0, StatusCode::CREATED);

    let appointment = serde_json::json!({
        "appointment_id": APPOINTMENT,
        "patient_id": PATIENT,
        "practitioner_id": PRACTITIONER,
        "scheduled_date": "2026-09-01",
        "slot": { "start": "09:00:00", "end": "09:30:00" },
        "buffer_duration": null,
        "status": "completed",
        "reason": null,
        "notes": null,
    });
    assert_eq!(post_json(router, "/api/appointments", appointment).await.0, StatusCode::CREATED);

    let invoice = serde_json::json!({
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
    assert_eq!(post_json(router, "/api/invoices", invoice).await.0, StatusCode::CREATED);

    let payment = serde_json::json!({
        "payment_id": "02020202-0202-0202-0202-020202020202",
        "amount": "75.00",
        "method": "card",
        "received_at": "2026-09-02T11:00:00Z",
    });
    let uri = format!("/api/invoices/{INVOICE}/payments");
    assert_eq!(post_json(router, &uri, payment).await.0, StatusCode::CREATED);
}

#[tokio::test]
async fn clinic_analytics_reflects_recorded_events() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };
    seed(&mut router).await;

    let (status, body) = get(&mut router, "/api/analytics/clinic").await;
    assert_eq!(status, StatusCode::OK, "{body}");

    let days = body["appointments_per_day"].as_array().unwrap();
    assert_eq!(days.len(), 1, "{body}");
    assert_eq!(days[0]["day"], "2026-09-01", "{body}");
    assert_eq!(days[0]["appointment_count"], 1, "{body}");

    assert_eq!(body["billed_total"], "125.00", "{body}");
    assert_eq!(body["paid_total"], "75.00", "{body}");

    let practitioners = body["practitioner_appointment_counts"].as_array().unwrap();
    assert_eq!(practitioners.len(), 1, "{body}");
    assert_eq!(practitioners[0]["practitioner_id"], PRACTITIONER, "{body}");
    assert_eq!(practitioners[0]["appointment_count"], 1, "{body}");
}

#[tokio::test]
async fn clinic_analytics_returns_zeroed_totals_with_no_events() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, body) = get(&mut router, "/api/analytics/clinic").await;
    assert_eq!(status, StatusCode::OK, "{body}");
    assert_eq!(body["appointments_per_day"].as_array().unwrap().len(), 0, "{body}");
    assert_eq!(body["practitioner_appointment_counts"].as_array().unwrap().len(), 0, "{body}");
    assert_eq!(body["billed_total"], "0.00", "{body}");
    assert_eq!(body["paid_total"], "0.00", "{body}");
}
