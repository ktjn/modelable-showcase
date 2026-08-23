//! Patient API (IMPLEMENTATION_PLAN.md Task 9.2).
//!
//! Uses the generated Patient request/reply types at the API boundaries and
//! persists to the generated `patient_db` table. Per the model, `patientId` is
//! client-supplied (the generated request projection only excludes `@server`
//! fields, and `patientId` is not `@server`), while `createdAt`/`updatedAt`
//! are server-generated. The generated `patient_db` DDL declares `patient_id`
//! as `PRIMARY KEY`, so duplicate creation is rejected atomically with
//! `INSERT ... ON CONFLICT (patient_id) DO NOTHING` returning 409.
//!
//! `GET /api/patients` supports synthetic search by name and/or email only.

use axum::extract::{Path, Query, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use chrono::{DateTime, Utc};
use clinic_core::patient::patient_address_v0::PatientAddressV0;
use clinic_core::patient::patient_contact_details_v0::PatientContactDetailsV0;
use clinic_core::patient::patient_id::PatientId;
use clinic_core::patient::patient_patient_reply_v2::PatientPatientReplyV2;
use clinic_core::patient::patient_patient_request_v2::PatientPatientRequestV2;
use std::str::FromStr;

use serde::Deserialize;
use showcase_core::patient as patient_core;
use sqlx::Row;
use uuid::Uuid;

use crate::http::{self, ApiError, JsonBody};
use crate::AppState;

const PATIENT_COLUMNS: &str = "patient_id, legal_name, preferred_name, date_of_birth, contact, \
     address, preferred_language, alternate_phone_numbers, notes, clinical_notes, created_at, \
     updated_at";

pub fn patient_routes() -> Router<AppState> {
    Router::new()
        .route("/api/patients", post(create_patient).get(list_patients))
        .route("/api/patients/{id}", get(get_patient))
}

fn row_to_reply(row: &sqlx::postgres::PgRow) -> Result<PatientPatientReplyV2, ApiError> {
    let patient_id: String = row
        .try_get("patient_id")
        .map_err(|err| ApiError::internal(format!("decoding patient_id: {err}")))?;
    let patient_id = PatientId(
        Uuid::from_str(&patient_id)
            .map_err(|err| ApiError::internal(format!("patient_id column is not a uuid: {err}")))?,
    );
    let legal_name: String = row
        .try_get("legal_name")
        .map_err(|err| ApiError::internal(format!("decoding legal_name: {err}")))?;
    let preferred_name: Option<String> = row
        .try_get("preferred_name")
        .map_err(|err| ApiError::internal(format!("decoding preferred_name: {err}")))?;
    let date_of_birth: chrono::NaiveDate = row
        .try_get("date_of_birth")
        .map_err(|err| ApiError::internal(format!("decoding date_of_birth: {err}")))?;
    let contact: sqlx::types::Json<PatientContactDetailsV0> = row
        .try_get("contact")
        .map_err(|err| ApiError::internal(format!("decoding contact: {err}")))?;
    let address: Option<sqlx::types::Json<PatientAddressV0>> = row
        .try_get("address")
        .map_err(|err| ApiError::internal(format!("decoding address: {err}")))?;
    let preferred_language: String = row
        .try_get("preferred_language")
        .map_err(|err| ApiError::internal(format!("decoding preferred_language: {err}")))?;
    let alternate_phone_numbers: Option<Vec<String>> = row
        .try_get("alternate_phone_numbers")
        .map_err(|err| ApiError::internal(format!("decoding alternate_phone_numbers: {err}")))?;
    let notes: Option<String> = row
        .try_get("notes")
        .map_err(|err| ApiError::internal(format!("decoding notes: {err}")))?;
    let clinical_notes: Option<String> = row
        .try_get("clinical_notes")
        .map_err(|err| ApiError::internal(format!("decoding clinical_notes: {err}")))?;
    let created_at: DateTime<Utc> = row
        .try_get("created_at")
        .map_err(|err| ApiError::internal(format!("decoding created_at: {err}")))?;
    let updated_at: Option<DateTime<Utc>> = row
        .try_get("updated_at")
        .map_err(|err| ApiError::internal(format!("decoding updated_at: {err}")))?;

    Ok(PatientPatientReplyV2 {
        patient_id,
        legal_name,
        preferred_name,
        date_of_birth,
        contact: contact.0,
        address: address.map(|value| value.0),
        preferred_language,
        alternate_phone_numbers,
        notes,
        clinical_notes,
        created_at,
        updated_at,
    })
}

// --- handlers -------------------------------------------------------------------

async fn create_patient(
    State(state): State<AppState>,
    JsonBody(request): JsonBody<PatientPatientRequestV2>,
) -> Result<(StatusCode, Json<PatientPatientReplyV2>), ApiError> {
    let created_at = http::utc_now();
    let db_row = patient_core::request_to_db(&request, created_at);

    // patient_id is the generated PK; atomic duplicate detection.
    let insert = sqlx::query(
        "INSERT INTO patient_db (patient_id, legal_name, preferred_name, date_of_birth, contact, \
         address, preferred_language, alternate_phone_numbers, notes, clinical_notes, created_at, \
         updated_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) \
         ON CONFLICT (patient_id) DO NOTHING",
    )
    .bind(db_row.patient_id.to_string())
    .bind(&db_row.legal_name)
    .bind(&db_row.preferred_name)
    .bind(db_row.date_of_birth)
    .bind(sqlx::types::Json(&db_row.contact))
    .bind(db_row.address.as_ref().map(sqlx::types::Json))
    .bind(&db_row.preferred_language)
    .bind(&db_row.alternate_phone_numbers)
    .bind(&db_row.notes)
    .bind(&db_row.clinical_notes)
    .bind(db_row.created_at)
    .bind(None::<DateTime<Utc>>)
    .execute(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("patient insert failed: {err}")))?;

    if insert.rows_affected() != 1 {
        return Err(ApiError::conflict(format!("patient {} already exists", db_row.patient_id.0)));
    }

    Ok((StatusCode::CREATED, Json(patient_core::db_to_reply(db_row))))
}

async fn get_patient(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<PatientPatientReplyV2>, ApiError> {
    let _parsed = Uuid::parse_str(&id)
        .map_err(|err| ApiError::bad_request(format!("invalid patient id '{id}': {err}")))?;

    let row = sqlx::query(&format!("SELECT {PATIENT_COLUMNS} FROM patient_db WHERE patient_id = $1"))
        .bind(&id)
        .fetch_optional(&state.pool)
        .await
        .map_err(|err| ApiError::internal(format!("patient lookup failed: {err}")))?;

    let row = row.ok_or_else(|| ApiError::not_found(format!("patient {id} not found")))?;
    Ok(Json(row_to_reply(&row)?))
}

#[derive(Deserialize, Default)]
#[serde(deny_unknown_fields)]
pub struct PatientSearch {
    pub name: Option<String>,
    pub email: Option<String>,
}

async fn list_patients(
    State(state): State<AppState>,
    Query(search): Query<PatientSearch>,
) -> Result<Json<Vec<PatientPatientReplyV2>>, ApiError> {
    let mut sql = format!("SELECT {PATIENT_COLUMNS} FROM patient_db WHERE 1 = 1");
    let mut params: Vec<String> = Vec::new();
    if let Some(name) = search.name.filter(|value| !value.is_empty()) {
        params.push(name);
        sql.push_str(&format!(" AND legal_name ILIKE '%' || ${} || '%'", params.len()));
    }
    if let Some(email) = search.email.filter(|value| !value.is_empty()) {
        params.push(email);
        sql.push_str(&format!(" AND contact ->> 'email' ILIKE '%' || ${} || '%'", params.len()));
    }
    sql.push_str(" ORDER BY created_at, patient_id");

    let mut query = sqlx::query(&sql);
    for param in &params {
        query = query.bind(param);
    }
    let rows = query
        .fetch_all(&state.pool)
        .await
        .map_err(|err| ApiError::internal(format!("patient list failed: {err}")))?;

    let replies = rows
        .iter()
        .map(row_to_reply)
        .collect::<Result<Vec<_>, _>>()?;
    Ok(Json(replies))
}
