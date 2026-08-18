//! Patient summary API (IMPLEMENTATION_PLAN.md Task 9.4).
//!
//! `GET /api/patients/:id/summary` returns a real multi-domain aggregation of a
//! patient's current state, composed from SQL across the patient, scheduling,
//! clinical, and billing tables (rather than Modelable runtime materialisation,
//! per the task spec). It preserves the generated projection semantics in the
//! field mapping: patient identity comes from `patient_db`; encounter/appointment
//! counts from `encounter_db`/`appointment_db`; invoice totals and payment sums
//! from `invoice_db`/`payment_db`.

use axum::extract::{Path, State};
use axum::routing::get;
use axum::{Json, Router};
use serde::Serialize;
use sqlx::Row;
use uuid::Uuid;

use crate::http::ApiError;
use crate::AppState;

pub fn summary_routes() -> Router<AppState> {
    Router::new().route("/api/patients/{id}/summary", get(patient_summary))
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PatientSummary {
    pub patient_id: String,
    pub legal_name: String,
    pub preferred_name: Option<String>,
    pub date_of_birth: chrono::NaiveDate,
    pub preferred_language: String,
    pub appointment_count: i64,
    pub encounter_count: i64,
    pub observation_count: i64,
    pub invoice_count: i64,
    pub total_invoiced: Option<String>,
    pub total_paid: Option<String>,
    pub outstanding: Option<String>,
    pub last_encounter_at: Option<chrono::DateTime<chrono::Utc>>,
}

async fn patient_summary(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<PatientSummary>, ApiError> {
    Uuid::parse_str(&id)
        .map_err(|err| ApiError::bad_request(format!("invalid patient id '{id}': {err}")))?;

    // Patient identity.
    let patient_row = sqlx::query(
        "SELECT patient_id, legal_name, preferred_name, date_of_birth, preferred_language \
         FROM patient_db WHERE patient_id = $1",
    )
    .bind(&id)
    .fetch_optional(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("patient summary lookup failed: {err}")))?;
    let patient_row = patient_row.ok_or_else(|| ApiError::not_found(format!("patient {id} not found")))?;
    let legal_name: String = patient_row
        .try_get("legal_name")
        .map_err(|err| ApiError::internal(format!("decoding legal_name: {err}")))?;
    let preferred_name: Option<String> = patient_row
        .try_get("preferred_name")
        .map_err(|err| ApiError::internal(format!("decoding preferred_name: {err}")))?;
    let date_of_birth: chrono::NaiveDate = patient_row
        .try_get("date_of_birth")
        .map_err(|err| ApiError::internal(format!("decoding date_of_birth: {err}")))?;
    let preferred_language: String = patient_row
        .try_get("preferred_language")
        .map_err(|err| ApiError::internal(format!("decoding preferred_language: {err}")))?;

    let appointment_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM appointment_db WHERE patient_id = $1",
    )
    .bind(&id)
    .fetch_one(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("appointment count failed: {err}")))?;

    let encounter_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM encounter_db WHERE patient_id = $1",
    )
    .bind(&id)
    .fetch_one(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("encounter count failed: {err}")))?;

    let observation_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM observation_db o JOIN encounter_db e ON o.encounter_id = e.encounter_id \
         WHERE e.patient_id = $1",
    )
    .bind(&id)
    .fetch_one(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("observation count failed: {err}")))?;

    let invoice_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM invoice_db WHERE patient_id = $1",
    )
    .bind(&id)
    .fetch_one(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("invoice count failed: {err}")))?;

    let total_invoiced: Option<String> = sqlx::query_scalar(
        "SELECT sum(total)::text FROM invoice_db WHERE patient_id = $1",
    )
    .bind(&id)
    .fetch_one(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("invoice total failed: {err}")))?;

    let total_paid: Option<String> = sqlx::query_scalar(
        "SELECT sum(p.amount)::text FROM payment_db p JOIN invoice_db i ON p.invoice_id = i.invoice_id \
         WHERE i.patient_id = $1",
    )
    .bind(&id)
    .fetch_one(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("payment total failed: {err}")))?;

    let outstanding: Option<String> = sqlx::query_scalar(
        "SELECT COALESCE(sum(total), 0)::text FROM invoice_db \
         WHERE patient_id = $1 AND status IN ('issued', 'overdue')",
    )
    .bind(&id)
    .fetch_one(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("outstanding total failed: {err}")))?;

    let last_encounter_at: Option<chrono::DateTime<chrono::Utc>> = sqlx::query_scalar(
        "SELECT max(started_at) FROM encounter_db WHERE patient_id = $1",
    )
    .bind(&id)
    .fetch_one(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("last encounter lookup failed: {err}")))?;

    Ok(Json(PatientSummary {
        patient_id: id,
        legal_name,
        preferred_name,
        date_of_birth,
        preferred_language,
        appointment_count,
        encounter_count,
        observation_count,
        invoice_count,
        total_invoiced,
        total_paid,
        outstanding,
        last_encounter_at,
    }))
}
