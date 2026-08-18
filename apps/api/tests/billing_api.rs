//! Task 9.4 integration tests: the generated Billing API against the
//! showcase PostgreSQL. These skip (early-return) when the showcase DB is
//! unreachable; run `docker compose up -d` to execute them for real.

use std::time::Duration;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use axum::Router;
use http_body_util::BodyExt;
use modelable_showcase_api::{app, AppState};
use serde_json::{json, Value};
use tower::ServiceExt;

const INVOICE: &str = "10101010-1010-1010-1010-101010101010";
const PATIENT: &str = "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d";

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
             to exercise the Billing API integration tests"
        );
        return None;
    }
    sqlx::query("TRUNCATE TABLE invoice_db CASCADE")
        .execute(&state.pool)
        .await
        .expect("failed to TRUNCATE invoice_db");
    sqlx::query("TRUNCATE TABLE payment_db CASCADE")
        .execute(&state.pool)
        .await
        .expect("failed to TRUNCATE payment_db");
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

fn invoice_body() -> Value {
    json!({
        "invoiceId": INVOICE,
        "patientId": PATIENT,
        "encounterId": null,
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
    })
}

#[tokio::test]
async fn invoice_creation_roundtrip() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, body) = post_json(&mut router, "/api/invoices", invoice_body()).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");
    assert_eq!(body["invoiceId"], INVOICE);
    assert_eq!(body["patientId"], PATIENT);
    assert_eq!(body["status"], "issued");
    assert_eq!(body["total"], "125.00");
    assert_eq!(body["lines"][0]["lineTotal"], "100.00");
    assert!(body["createdAt"].is_string(), "{body}");
}

#[tokio::test]
async fn invoice_duplicate_returns_conflict() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, _) = post_json(&mut router, "/api/invoices", invoice_body()).await;
    assert_eq!(status, StatusCode::CREATED);

    let (status, body) = post_json(&mut router, "/api/invoices", invoice_body()).await;
    assert_eq!(status, StatusCode::CONFLICT, "{body}");
}

#[tokio::test]
async fn invoice_invalid_inputs_are_rejected() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let mut bad = invoice_body();
    bad["invoiceId"] = json!("not-a-uuid");
    let (status, body) = post_json(&mut router, "/api/invoices", bad).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    let mut bad = invoice_body();
    bad["status"] = json!("cancelled");
    let (status, body) = post_json(&mut router, "/api/invoices", bad).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");
}

#[tokio::test]
async fn payment_added_to_existing_invoice() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, _) = post_json(&mut router, "/api/invoices", invoice_body()).await;
    assert_eq!(status, StatusCode::CREATED);

    let payment = json!({
        "paymentId": "02020202-0202-0202-0202-020202020202",
        "amount": "125.00",
        "method": "card",
        "receivedAt": "2026-09-02T11:00:00Z",
    });
    let uri = format!("/api/invoices/{INVOICE}/payments");
    let (status, body) = post_json(&mut router, &uri, payment).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");
    assert_eq!(body["invoiceId"], INVOICE);
    assert_eq!(body["amount"], "125.00");
    assert_eq!(body["method"], "card");
}

#[tokio::test]
async fn payment_for_unknown_invoice_returns_404() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let payment = json!({
        "paymentId": "02020202-0202-0202-0202-020202020202",
        "amount": "125.00",
        "method": "card",
        "receivedAt": "2026-09-02T11:00:00Z",
    });
    let uri = "/api/invoices/00000000-0000-0000-0000-000000000000/payments";
    let (status, body) = post_json(&mut router, uri, payment).await;
    assert_eq!(status, StatusCode::NOT_FOUND, "{body}");
}
