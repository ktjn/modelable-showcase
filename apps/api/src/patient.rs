//! Patient API (IMPLEMENTATION_PLAN.md Task 9.2).
//!
//! Uses the generated Patient request/reply types at the API boundaries and
//! persists to the generated `patient_db` table. Per the model, `patientId` is
//! client-supplied (the generated request projection only excludes `@server`
//! fields, and `patientId` is not `@server`), while `createdAt`/`updatedAt`
//! are server-generated. The generated `patient_db` DDL carries no unique
//! constraint on `patient_id`, so duplicate creation is detected with an
//! explicit existence check (check-then-insert) returning 409.
//!
//! `GET /api/patients` supports synthetic search by name and/or email only.

use std::str::FromStr;

use axum::body::Bytes;
use axum::extract::{FromRequest, Path, Query, Request, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use clinic_core::patient::patient_address_v0::PatientAddressV0;
use clinic_core::patient::patient_contact_details_v0::PatientContactDetailsV0;
use clinic_core::patient::patient_id::PatientId;
use clinic_core::patient::patient_patient_db_v2::PatientPatientDbV2;
use clinic_core::patient::patient_patient_reply_v2::PatientPatientReplyV2;
use clinic_core::patient::patient_patient_request_v2::PatientPatientRequestV2;
use chrono::{DateTime, NaiveDate, SecondsFormat, Utc};
use serde::Deserialize;
use sqlx::Row;
use uuid::Uuid;

use crate::AppState;

const PATIENT_COLUMNS: &str = "patient_id, legal_name, preferred_name, date_of_birth, contact, \
     address, preferred_language, alternate_phone_numbers, notes, clinical_notes, created_at, \
     updated_at";

pub fn patient_routes() -> Router<AppState> {
    Router::new()
        .route("/api/patients", post(create_patient).get(list_patients))
        .route("/api/patients/{id}", get(get_patient))
}

// --- error type ---------------------------------------------------------------

pub struct ApiError {
    pub status: StatusCode,
    pub message: String,
}

impl ApiError {
    fn bad_request(message: impl Into<String>) -> Self {
        Self { status: StatusCode::BAD_REQUEST, message: message.into() }
    }

    fn not_found(message: impl Into<String>) -> Self {
        Self { status: StatusCode::NOT_FOUND, message: message.into() }
    }

    fn conflict(message: impl Into<String>) -> Self {
        Self { status: StatusCode::CONFLICT, message: message.into() }
    }

    fn internal(message: impl Into<String>) -> Self {
        tracing::error!("{}", message.into());
        Self { status: StatusCode::INTERNAL_SERVER_ERROR, message: "internal server error".into() }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (self.status, Json(serde_json::json!({ "error": self.message }))).into_response()
    }
}

// --- body extractor with a deterministic 400 JSON rejection --------------------

pub struct JsonBody<T>(pub T);

impl<S, T> FromRequest<S> for JsonBody<T>
where
    S: Send + Sync,
    T: serde::de::DeserializeOwned,
{
    type Rejection = ApiError;

    async fn from_request(req: Request, state: &S) -> Result<Self, Self::Rejection> {
        let bytes = Bytes::from_request(req, state)
            .await
            .map_err(|err| ApiError::bad_request(format!("invalid request body: {err}")))?;
        let value = serde_json::from_slice(&bytes)
            .map_err(|err| ApiError::bad_request(format!("invalid request body: {err}")))?;
        Ok(JsonBody(value))
    }
}

// --- mapping helpers ------------------------------------------------------------

pub fn request_to_db(
    request: &PatientPatientRequestV2,
    created_at: &str,
) -> PatientPatientDbV2 {
    PatientPatientDbV2 {
        patient_id: request.patient_id,
        legal_name: request.legal_name.clone(),
        date_of_birth: request.date_of_birth.clone(),
        contact: request.contact.clone(),
        preferred_language: request.preferred_language.clone(),
        created_at: created_at.to_string(),
        preferred_name: request.preferred_name.clone(),
        address: request.address.clone(),
        alternate_phone_numbers: request.alternate_phone_numbers.clone(),
        notes: request.notes.clone(),
        clinical_notes: request.clinical_notes.clone(),
        updated_at: None,
    }
}

pub fn db_to_reply(db: PatientPatientDbV2) -> PatientPatientReplyV2 {
    PatientPatientReplyV2 {
        patient_id: db.patient_id,
        legal_name: db.legal_name,
        date_of_birth: db.date_of_birth,
        contact: db.contact,
        preferred_language: db.preferred_language,
        created_at: db.created_at,
        preferred_name: db.preferred_name,
        address: db.address,
        alternate_phone_numbers: db.alternate_phone_numbers,
        notes: db.notes,
        clinical_notes: db.clinical_notes,
        updated_at: db.updated_at,
    }
}

fn parse_date(value: &str) -> Result<NaiveDate, ApiError> {
    NaiveDate::parse_from_str(value, "%Y-%m-%d")
        .map_err(|err| ApiError::bad_request(format!("invalid date '{value}': {err}")))
}

fn parse_timestamp(value: &str) -> Result<DateTime<Utc>, ApiError> {
    DateTime::parse_from_rfc3339(value)
        .map(|dt| dt.with_timezone(&Utc))
        .map_err(|err| ApiError::bad_request(format!("invalid timestamp '{value}': {err}")))
}

fn utc_now_rfc3339() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true)
}

fn json<T: serde::Serialize>(value: &T) -> Result<String, ApiError> {
    serde_json::to_string(value).map_err(|err| ApiError::internal(format!("serialization failed: {err}")))
}

fn row_to_reply(row: &sqlx::postgres::PgRow) -> Result<PatientPatientReplyV2, ApiError> {
    let patient_id: String = row.try_get("patient_id")
        .map_err(|err| ApiError::internal(format!("decoding patient_id: {err}")))?;
    let legal_name: String = row.try_get("legal_name")
        .map_err(|err| ApiError::internal(format!("decoding legal_name: {err}")))?;
    let preferred_name: Option<String> = row.try_get("preferred_name")
        .map_err(|err| ApiError::internal(format!("decoding preferred_name: {err}")))?;
    let date_of_birth: NaiveDate = row.try_get("date_of_birth")
        .map_err(|err| ApiError::internal(format!("decoding date_of_birth: {err}")))?;
    let contact: String = row.try_get("contact")
        .map_err(|err| ApiError::internal(format!("decoding contact: {err}")))?;
    let address: Option<String> = row.try_get("address")
        .map_err(|err| ApiError::internal(format!("decoding address: {err}")))?;
    let preferred_language: String = row.try_get("preferred_language")
        .map_err(|err| ApiError::internal(format!("decoding preferred_language: {err}")))?;
    let alternate_phone_numbers: Option<Vec<String>> = row.try_get("alternate_phone_numbers")
        .map_err(|err| ApiError::internal(format!("decoding alternate_phone_numbers: {err}")))?;
    let notes: Option<String> = row.try_get("notes")
        .map_err(|err| ApiError::internal(format!("decoding notes: {err}")))?;
    let clinical_notes: Option<String> = row.try_get("clinical_notes")
        .map_err(|err| ApiError::internal(format!("decoding clinical_notes: {err}")))?;
    let created_at: DateTime<Utc> = row.try_get("created_at")
        .map_err(|err| ApiError::internal(format!("decoding created_at: {err}")))?;
    let updated_at: Option<DateTime<Utc>> = row.try_get("updated_at")
        .map_err(|err| ApiError::internal(format!("decoding updated_at: {err}")))?;

    let contact = serde_json::from_str::<PatientContactDetailsV0>(&contact)
        .map_err(|err| ApiError::internal(format!("contact column is not valid JSON: {err}")))?;
    let address = address
        .map(|value| serde_json::from_str::<PatientAddressV0>(&value))
        .transpose()
        .map_err(|err| ApiError::internal(format!("address column is not valid JSON: {err}")))?;

    Ok(PatientPatientReplyV2 {
        patient_id: PatientId(Uuid::from_str(&patient_id)
            .map_err(|err| ApiError::internal(format!("patient_id column is not a uuid: {err}")))?),
        legal_name,
        preferred_name,
        date_of_birth: date_of_birth.format("%Y-%m-%d").to_string(),
        contact,
        address,
        preferred_language,
        alternate_phone_numbers,
        notes,
        clinical_notes,
        created_at: created_at.to_rfc3339_opts(SecondsFormat::Secs, true),
        updated_at: updated_at.map(|value| value.to_rfc3339_opts(SecondsFormat::Secs, true)),
    })
}

// --- handlers -------------------------------------------------------------------

async fn create_patient(
    State(state): State<AppState>,
    JsonBody(request): JsonBody<PatientPatientRequestV2>,
) -> Result<(StatusCode, Json<PatientPatientReplyV2>), ApiError> {
    parse_date(&request.date_of_birth)?;
    let patient_id = request.patient_id.to_string();

    let exists = sqlx::query_scalar::<_, i32>("SELECT 1 FROM patient_db WHERE patient_id = $1")
        .bind(&patient_id)
        .fetch_optional(&state.pool)
        .await
        .map_err(|err| ApiError::internal(format!("duplicate check failed: {err}")))?;
    if exists.is_some() {
        return Err(ApiError::conflict(format!("patient {patient_id} already exists")));
    }

    let created_at = utc_now_rfc3339();
    let db_row = request_to_db(&request, &created_at);

    let insert = sqlx::query(
        "INSERT INTO patient_db (patient_id, legal_name, preferred_name, date_of_birth, contact, \
         address, preferred_language, alternate_phone_numbers, notes, clinical_notes, created_at, \
         updated_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
    )
    .bind(db_row.patient_id.to_string())
    .bind(&db_row.legal_name)
    .bind(db_row.preferred_name.clone())
    .bind(parse_date(&db_row.date_of_birth)?)
    .bind(json(&db_row.contact)?)
    .bind(db_row.address.as_ref().map(json).transpose()?)
    .bind(&db_row.preferred_language)
    .bind(db_row.alternate_phone_numbers.clone())
    .bind(db_row.notes.clone())
    .bind(db_row.clinical_notes.clone())
    .bind(parse_timestamp(&db_row.created_at)?)
    .bind(None::<DateTime<Utc>>)
    .execute(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("patient insert failed: {err}")))?;

    if insert.rows_affected() != 1 {
        return Err(ApiError::internal("patient insert affected no rows"));
    }

    Ok((StatusCode::CREATED, Json(db_to_reply(db_row))))
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
        sql.push_str(&format!(" AND contact::jsonb ->> 'email' ILIKE '%' || ${} || '%'", params.len()));
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