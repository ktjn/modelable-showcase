//! Shared operation vectors executed through the real Axum/PostgreSQL/ClickHouse runtime.

use std::collections::BTreeMap;
use std::time::Duration;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use axum::Router;
use http_body_util::BodyExt;
use modelable_showcase_api::{app, AppState};
use serde::Deserialize;
use serde_json::Value;
use tower::ServiceExt;

const VECTORS: &str = include_str!("../../../tests/parity/runtime-parity.json");

#[derive(Debug, Deserialize)]
struct VectorSuite {
    version: u32,
    scenarios: Vec<Scenario>,
}

#[derive(Debug, Deserialize)]
struct Scenario {
    name: String,
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

async fn db_lock() -> tokio::sync::MutexGuard<'static, ()> {
    static LOCK: tokio::sync::Mutex<()> = tokio::sync::Mutex::const_new(());
    LOCK.lock().await
}

async fn app_ready() -> Option<Router> {
    let state = AppState::default();
    let postgres = tokio::time::timeout(
        Duration::from_secs(4),
        sqlx::query_scalar::<_, i32>("SELECT 1").fetch_one(&state.pool),
    )
    .await
    .is_ok_and(|result| result.is_ok());
    let clickhouse = tokio::time::timeout(
        Duration::from_secs(4),
        state.clickhouse.query("SELECT 1").execute(),
    )
    .await
    .is_ok_and(|result| result.is_ok());
    if !(postgres && clickhouse) {
        eprintln!("SKIP: showcase PostgreSQL/ClickHouse unreachable; run 'docker compose up -d'");
        return None;
    }

    for table in [
        "patient_db",
        "appointment_db",
        "encounter_db",
        "observation_db",
        "invoice_db",
        "payment_db",
    ] {
        sqlx::query(&format!("TRUNCATE TABLE {table} CASCADE"))
            .execute(&state.pool)
            .await
            .unwrap_or_else(|error| panic!("failed to truncate {table}: {error}"));
    }
    for table in ["appointment_event", "invoice_event", "payment_event"] {
        state
            .clickhouse
            .query(&format!("TRUNCATE TABLE {table}"))
            .execute()
            .await
            .unwrap_or_else(|error| panic!("failed to truncate {table}: {error}"));
    }
    Some(app(state))
}

#[tokio::test]
async fn application_vectors_match_the_native_http_runtime() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else {
        return;
    };
    let suite: VectorSuite =
        serde_json::from_str(VECTORS).expect("parity vectors must be valid JSON");
    assert_eq!(suite.version, 1, "unsupported parity vector version");

    for scenario in suite.scenarios {
        for step in scenario.steps {
            let (status, body) = call(&mut router, &step).await;
            assert_eq!(
                category(status),
                step.expect.category,
                "scenario '{}', step '{}', status {status}, body {body}",
                scenario.name,
                step.name
            );
            if status.is_success() {
                assert_fields(&scenario.name, &step, &body);
            }
        }
    }
}

async fn call(router: &mut Router, step: &Step) -> (StatusCode, Value) {
    let mut request = Request::builder()
        .method(step.method.as_str())
        .uri(&step.path);
    let body = match &step.body {
        Some(body) => {
            request = request.header("content-type", "application/json");
            Body::from(body.to_string())
        }
        None => Body::empty(),
    };
    let response = router
        .oneshot(request.body(body).expect("valid vector request"))
        .await
        .unwrap();
    let status = response.status();
    let bytes = response.into_body().collect().await.unwrap().to_bytes();
    let body = serde_json::from_slice(&bytes)
        .unwrap_or_else(|_| Value::String(String::from_utf8_lossy(&bytes).into_owned()));
    (status, body)
}

fn category(status: StatusCode) -> &'static str {
    match status {
        status if status.is_success() => "ok",
        StatusCode::BAD_REQUEST | StatusCode::UNPROCESSABLE_ENTITY => "bad_request",
        StatusCode::NOT_FOUND => "not_found",
        StatusCode::CONFLICT => "conflict",
        _ => "internal",
    }
}

fn assert_fields(scenario: &str, step: &Step, body: &Value) {
    for (pointer, expected) in &step.expect.fields {
        assert_eq!(
            body.pointer(pointer),
            Some(expected),
            "scenario '{scenario}', step '{}', field '{pointer}', body {body}",
            step.name
        );
    }
}
