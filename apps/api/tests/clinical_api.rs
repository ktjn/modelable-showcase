//! Task 9.4 integration tests: the generated Clinical API against the
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

const ENCOUNTER: &str = "e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1";
const PATIENT: &str = "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d";
const PRACTITIONER: &str = "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1";

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
             to exercise the Clinical API integration tests"
        );
        return None;
    }
    sqlx::query("TRUNCATE TABLE encounter_db CASCADE")
        .execute(&state.pool)
        .await
        .expect("failed to TRUNCATE encounter_db");
    sqlx::query("TRUNCATE TABLE observation_db CASCADE")
        .execute(&state.pool)
        .await
        .expect("failed to TRUNCATE observation_db");
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

async fn patch_json(router: &mut Router, uri: &str, body: Value) -> (StatusCode, Value) {
    let request = Request::builder()
        .method("PATCH")
        .uri(uri)
        .header("content-type", "application/json")
        .body(Body::from(body.to_string()))
        .unwrap();
    call(router, request).await
}

fn encounter_body() -> Value {
    json!({
        "encounterId": ENCOUNTER,
        "patientId": PATIENT,
        "practitionerId": PRACTITIONER,
        "appointmentId": null,
        "status": "in_progress",
        "startedAt": "2026-09-01T09:00:00Z",
        "endedAt": null,
        "expectedDuration": null,
        "reasonCode": null,
        "diagnoses": null,
    })
}

#[tokio::test]
async fn encounter_creation_roundtrip() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, body) = post_json(&mut router, "/api/encounters", encounter_body()).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");
    assert_eq!(body["encounterId"], ENCOUNTER);
    assert_eq!(body["patientId"], PATIENT);
    assert_eq!(body["practitionerId"], PRACTITIONER);
    assert_eq!(body["status"], "in_progress");
    assert!(body["createdAt"].is_string(), "{body}");
    assert!(body["updatedAt"].is_null(), "{body}");
}

#[tokio::test]
async fn encounter_complete_sets_status_and_ended_at() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, _) = post_json(&mut router, "/api/encounters", encounter_body()).await;
    assert_eq!(status, StatusCode::CREATED);

    let uri = format!("/api/encounters/{ENCOUNTER}");
    let (status, body) = patch_json(&mut router, &uri, json!({ "status": "completed" })).await;
    assert_eq!(status, StatusCode::OK, "{body}");
    assert_eq!(body["status"], "completed", "{body}");
    assert!(body["endedAt"].is_string(), "{body}");
    assert!(body["updatedAt"].is_string(), "{body}");
}

#[tokio::test]
async fn encounter_cancel_sets_status() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, _) = post_json(&mut router, "/api/encounters", encounter_body()).await;
    assert_eq!(status, StatusCode::CREATED);

    let uri = format!("/api/encounters/{ENCOUNTER}");
    let (status, body) = patch_json(&mut router, &uri, json!({ "status": "cancelled" })).await;
    assert_eq!(status, StatusCode::OK, "{body}");
    assert_eq!(body["status"], "cancelled", "{body}");
}

#[tokio::test]
async fn encounter_update_after_cancel_is_rejected() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, _) = post_json(&mut router, "/api/encounters", encounter_body()).await;
    assert_eq!(status, StatusCode::CREATED);

    let uri = format!("/api/encounters/{ENCOUNTER}");
    let (status, _) = patch_json(&mut router, &uri, json!({ "status": "cancelled" })).await;
    assert_eq!(status, StatusCode::OK);

    let (status, body) = patch_json(&mut router, &uri, json!({ "status": "completed" })).await;
    assert_eq!(status, StatusCode::CONFLICT, "{body}");
}

#[tokio::test]
async fn encounter_update_for_unknown_encounter_returns_404() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let uri = "/api/encounters/00000000-0000-0000-0000-000000000000";
    let (status, body) = patch_json(&mut router, uri, json!({ "status": "completed" })).await;
    assert_eq!(status, StatusCode::NOT_FOUND, "{body}");
}

#[tokio::test]
async fn encounter_update_with_invalid_status_returns_400() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, _) = post_json(&mut router, "/api/encounters", encounter_body()).await;
    assert_eq!(status, StatusCode::CREATED);

    let uri = format!("/api/encounters/{ENCOUNTER}");
    let (status, body) = patch_json(&mut router, &uri, json!({ "status": "scheduled" })).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");
}

#[tokio::test]
async fn encounter_duplicate_returns_conflict() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, _) = post_json(&mut router, "/api/encounters", encounter_body()).await;
    assert_eq!(status, StatusCode::CREATED);

    let (status, body) = post_json(&mut router, "/api/encounters", encounter_body()).await;
    assert_eq!(status, StatusCode::CONFLICT, "{body}");
}

#[tokio::test]
async fn encounter_invalid_inputs_are_rejected() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let mut bad = encounter_body();
    bad["encounterId"] = json!("not-a-uuid");
    let (status, body) = post_json(&mut router, "/api/encounters", bad).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    let mut bad = encounter_body();
    bad["status"] = json!("scheduled");
    let (status, body) = post_json(&mut router, "/api/encounters", bad).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");
}

#[tokio::test]
async fn observation_added_to_existing_encounter() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, _) = post_json(&mut router, "/api/encounters", encounter_body()).await;
    assert_eq!(status, StatusCode::CREATED);

    let observation = json!({
        "observationId": "01010101-0101-0101-0101-010101010101",
        "code": "temperature",
        "temperatureCelsius": 36.8,
        "bloodPressureSystolic": 120,
        "bloodPressureDiastolic": 80,
        "pulseBpm": 72,
        "isAbnormal": false,
        "deviceId": null,
        "metadata": { "unit": "celsius" },
        "recordedAt": "2026-09-01T09:15:00Z",
    });
    let uri = format!("/api/encounters/{ENCOUNTER}/observations");
    let (status, body) = post_json(&mut router, &uri, observation).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");
    assert_eq!(body["encounterId"], ENCOUNTER);
    assert_eq!(body["code"], "temperature");
    assert_eq!(body["temperatureCelsius"], 36.8);
    assert_eq!(body["isAbnormal"], false);
}

#[tokio::test]
async fn observation_for_unknown_encounter_returns_404() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let observation = json!({
        "observationId": "01010101-0101-0101-0101-010101010101",
        "code": "temperature",
        "isAbnormal": false,
        "recordedAt": "2026-09-01T09:15:00Z",
    });
    let uri = "/api/encounters/00000000-0000-0000-0000-000000000000/observations";
    let (status, body) = post_json(&mut router, uri, observation).await;
    assert_eq!(status, StatusCode::NOT_FOUND, "{body}");
}
