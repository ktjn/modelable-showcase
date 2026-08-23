//! Modelable Showcase HTTP API (IMPLEMENTATION_PLAN.md Task 9.1).
//!
//! Bootstraps the Axum API and wires it to the generated Rust contract
//! package `clinic-core` (patient + scheduling domains) by local path, so the
//! API build fails whenever the generated Rust contracts stop compiling.
//!
//! Endpoints:
//!   GET /health - liveness; also reports the generated contract linkage.
//!   GET /ready  - readiness; probes PostgreSQL and ClickHouse connectivity
//!                 using the same SHOWCASE_PG_* / SHOWCASE_CH_* environment
//!                 variables as scripts/apply-postgres-ddl.py and
//!                 scripts/apply-clickhouse-ddl.py (defaults 127.0.0.1:5433
//!                 showcase/showcase and 127.0.0.1:8123 showcase/showcase).
//!
//! Readiness checks are injected as async closures so unit tests exercise the
//! endpoint logic hermetically; the default state wires the real SQLx and
//! ClickHouse clients.

use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use std::time::Duration;

use axum::extract::State;
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::{Json, Router};
use serde::Serialize;
use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;

pub mod analytics;
pub mod billing;
pub mod clinical;
pub mod docs;
pub mod http;
pub mod patient;
pub mod scheduling;
pub mod summary;

pub type ReadyFn = Arc<
    dyn Fn() -> Pin<Box<dyn Future<Output = bool> + Send>> + Send + Sync,
>;

/// Readiness probe closures and the lazy persistence pool, injectable for
/// hermetic tests.
#[derive(Clone)]
pub struct AppState {
    pub postgres_check: ReadyFn,
    pub clickhouse_check: ReadyFn,
    pub pool: PgPool,
    pub clickhouse: clickhouse::Client,
}

fn wrap_ready(
    f: impl Fn() -> Pin<Box<dyn Future<Output = bool> + Send>> + Send + Sync + 'static,
) -> ReadyFn {
    Arc::new(f)
}

pub fn lazy_pool() -> PgPool {
    let config = PostgresConfig::default();
    let url = format!(
        "postgresql://{}:{}@{}:{}/{}",
        config.user, config.password, config.host, config.port, config.dbname
    );
    PgPoolOptions::new()
        .max_connections(5)
        .connect_lazy(&url)
        .expect("malformed SHOWCASE_PG_* configuration - cannot build the Postgres pool")
}

pub fn lazy_clickhouse() -> clickhouse::Client {
    let config = ClickHouseConfig::default();
    clickhouse::Client::default()
        .with_url(format!("http://{}:{}", config.host, config.port))
        .with_user(config.user)
        .with_password(config.password)
        .with_database(config.dbname)
        // The analytics module (Task 9.5) writes a deliberate column subset
        // to each generated event table (e.g. omitting `notes`/`reason`);
        // server-side defaults fill the rest. The crate's schema-validated
        // insert path rejects any column absent from the Rust row type, even
        // if it is Nullable, so validation is disabled for these writes.
        .with_validation(false)
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            postgres_check: wrap_ready(|| Box::pin(postgres_is_reachable())),
            clickhouse_check: wrap_ready(|| Box::pin(clickhouse_is_reachable())),
            pool: lazy_pool(),
            clickhouse: lazy_clickhouse(),
        }
    }
}

pub fn app(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/ready", get(ready))
        .merge(patient::patient_routes())
        .merge(scheduling::scheduling_routes())
        .merge(clinical::clinical_routes())
        .merge(billing::billing_routes())
        .merge(summary::summary_routes())
        .merge(analytics::analytics_routes())
        .merge(docs::docs_routes())
        .with_state(state)
}

// --- configuration (shared env-var contract with the Python DB scripts) -----

pub struct PostgresConfig {
    pub host: String,
    pub port: String,
    pub user: String,
    pub password: String,
    pub dbname: String,
}

impl Default for PostgresConfig {
    fn default() -> Self {
        Self {
            host: std::env::var("SHOWCASE_PG_HOST").unwrap_or_else(|_| "127.0.0.1".into()),
            port: std::env::var("SHOWCASE_PG_PORT").unwrap_or_else(|_| "5433".into()),
            user: std::env::var("SHOWCASE_PG_USER").unwrap_or_else(|_| "showcase".into()),
            password: std::env::var("SHOWCASE_PG_PASSWORD").unwrap_or_else(|_| "showcase".into()),
            dbname: std::env::var("SHOWCASE_PG_DBNAME").unwrap_or_else(|_| "showcase".into()),
        }
    }
}

pub struct ClickHouseConfig {
    pub host: String,
    pub port: String,
    pub user: String,
    pub password: String,
    pub dbname: String,
}

impl Default for ClickHouseConfig {
    fn default() -> Self {
        Self {
            host: std::env::var("SHOWCASE_CH_HOST").unwrap_or_else(|_| "127.0.0.1".into()),
            port: std::env::var("SHOWCASE_CH_PORT").unwrap_or_else(|_| "8123".into()),
            user: std::env::var("SHOWCASE_CH_USER").unwrap_or_else(|_| "showcase".into()),
            password: std::env::var("SHOWCASE_CH_PASSWORD").unwrap_or_else(|_| "showcase".into()),
            dbname: std::env::var("SHOWCASE_CH_DBNAME").unwrap_or_else(|_| "showcase".into()),
        }
    }
}

// --- generated contract linkage (Task 9.1: API build must fail if the
// generated Rust contracts stop compiling) -----------------------------------

pub mod contract {
    use clinic_core::patient::patient_id::PatientId;
    use clinic_core::patient::patient_patient_v2::PatientPatientV2;

    pub const PATIENT_SCHEMA_VERSION: u32 = PatientPatientV2::SCHEMA_VERSION;
    pub const PATIENT_REGISTRY_ID: u32 = PatientId::REGISTRY_ID;
    pub const PATIENT_CONTENT_SIGNATURE: [u8; 32] = PatientPatientV2::SCHEMA_CONTENT_SIGNATURE;
}

// --- readiness probes ---------------------------------------------------------

pub async fn postgres_is_reachable() -> bool {
    let cfg = PostgresConfig::default();
    let url = format!(
        "postgresql://{}:{}@{}:{}/{}",
        cfg.user, cfg.password, cfg.host, cfg.port, cfg.dbname
    );
    tokio::time::timeout(Duration::from_secs(4), async move {
        let pool = sqlx::postgres::PgPoolOptions::new()
            .max_connections(1)
            .connect(&url)
            .await;
        match pool {
            Ok(pool) => {
                let ok = sqlx::query_scalar::<_, i32>("SELECT 1").fetch_one(&pool).await.is_ok();
                pool.close().await;
                ok
            }
            Err(_) => false,
        }
    })
    .await
    .unwrap_or(false)
}

pub async fn clickhouse_is_reachable() -> bool {
    let cfg = ClickHouseConfig::default();
    let client = clickhouse::Client::default()
        .with_url(format!("http://{}:{}", cfg.host, cfg.port))
        .with_user(cfg.user)
        .with_password(cfg.password)
        .with_database(cfg.dbname);
    tokio::time::timeout(Duration::from_secs(4), async move {
        client.query("SELECT 1").execute().await
    })
    .await
    .map(|result| result.is_ok())
    .unwrap_or(false)
}

// --- handlers -----------------------------------------------------------------

#[derive(Serialize)]
struct HealthBody {
    status: &'static str,
    contract: HealthContractBody,
}

#[derive(Serialize)]
struct HealthContractBody {
    patient_schema_version: u32,
    patient_registry_id: u32,
    patient_content_signature: [u8; 32],
}

async fn health() -> impl IntoResponse {
    Json(HealthBody {
        status: "ok",
        contract: HealthContractBody {
            patient_schema_version: contract::PATIENT_SCHEMA_VERSION,
            patient_registry_id: contract::PATIENT_REGISTRY_ID,
            patient_content_signature: contract::PATIENT_CONTENT_SIGNATURE,
        },
    })
}

#[derive(Serialize)]
struct ReadyBody {
    status: &'static str,
    postgres: bool,
    clickhouse: bool,
}

async fn ready(State(state): State<AppState>) -> impl IntoResponse {
    let postgres = (state.postgres_check)().await;
    let clickhouse = (state.clickhouse_check)().await;
    let (status, status_label) = if postgres && clickhouse {
        (StatusCode::OK, "ready")
    } else {
        (StatusCode::SERVICE_UNAVAILABLE, "not_ready")
    };
    (
        status,
        Json(ReadyBody {
            status: status_label,
            postgres,
            clickhouse,
        }),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::Request;
    use http_body_util::BodyExt;
    use tower::ServiceExt;

    fn stub_ready(value: bool) -> ReadyFn {
        wrap_ready(move || Box::pin(async move { value }))
    }

    fn stub_state(postgres: bool, clickhouse: bool) -> AppState {
        AppState {
            postgres_check: stub_ready(postgres),
            clickhouse_check: stub_ready(clickhouse),
            pool: lazy_pool(),
            clickhouse: lazy_clickhouse(),
        }
    }

    async fn call(app: Router, uri: &str) -> (StatusCode, serde_json::Value) {
        let response = app
            .oneshot(Request::builder().uri(uri).body(Body::empty()).unwrap())
            .await
            .unwrap();
        let status = response.status();
        let bytes = response.into_body().collect().await.unwrap().to_bytes();
        let body = serde_json::from_slice(&bytes).unwrap();
        (status, body)
    }

    #[tokio::test]
    async fn health_returns_ok_with_generated_contract_linkage() {
        let (status, body) = call(app(stub_state(true, true)), "/health").await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["status"], "ok");
        assert_eq!(body["contract"]["patient_schema_version"], 2);
        assert_eq!(body["contract"]["patient_registry_id"], 2);
        assert_eq!(
            body["contract"]["patient_content_signature"].as_array().unwrap().len(),
            32
        );
    }

    #[tokio::test]
    async fn ready_returns_200_when_both_reachable() {
        let (status, body) = call(app(stub_state(true, true)), "/ready").await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["status"], "ready");
        assert_eq!(body["postgres"], true);
        assert_eq!(body["clickhouse"], true);
    }

    #[tokio::test]
    async fn ready_returns_503_when_postgres_down() {
        let (status, body) = call(app(stub_state(false, true)), "/ready").await;
        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["status"], "not_ready");
        assert_eq!(body["postgres"], false);
        assert_eq!(body["clickhouse"], true);
    }

    #[tokio::test]
    async fn ready_returns_503_when_clickhouse_down() {
        let (status, body) = call(app(stub_state(true, false)), "/ready").await;
        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["status"], "not_ready");
        assert_eq!(body["postgres"], true);
        assert_eq!(body["clickhouse"], false);
    }

    #[tokio::test]
    async fn ready_returns_200_against_real_showcase_dbs_when_reachable() {
        let state = AppState::default();
        let (postgres, clickhouse) =
            ((state.postgres_check)().await, (state.clickhouse_check)().await);
        if !(postgres && clickhouse) {
            eprintln!(
                "SKIP: showcase PostgreSQL/ClickHouse not both reachable \
                 (postgres={postgres}, clickhouse={clickhouse}); run 'docker compose up -d' \
                 and re-run to assert real /ready 200"
            );
            return;
        }
        let (status, body) = call(app(state), "/ready").await;
        assert_eq!(status, StatusCode::OK, "{body}");
        assert_eq!(body["status"], "ready", "{body}");
    }

    #[test]
    fn generated_contract_constants_match_pinned_showcase_reality() {
        assert_eq!(contract::PATIENT_SCHEMA_VERSION, 2);
        assert_eq!(contract::PATIENT_REGISTRY_ID, 2);
    }
}
