//! Clinical API (IMPLEMENTATION_PLAN.md Task 9.4).
//!
//! Uses the generated Encounter request/reply types at the API boundary and
//! persists to the generated `encounter_db` table, including its foreign key to
//! `appointment_db`. Observation is an event-only model with no generated table at
//! all, so this API persists observations to a hand-written `observation_db`
//! table instead. EncounterId/PatientId/PractitionerId are client-supplied
//! (the generated request projection only excludes `@server` fields);
//! createdAt/updatedAt are server-generated.

use std::str::FromStr;

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{patch, post};
use axum::{Json, Router};
use chrono::{DateTime, Utc};
use clinical_core::clinical::clinical_encounter_db_v1::ClinicalEncounterDbV1Status;
use clinical_core::clinical::clinical_encounter_reply_v1::{
    ClinicalEncounterReplyV1, ClinicalEncounterReplyV1Status,
};
use clinical_core::clinical::clinical_encounter_request_v1::ClinicalEncounterRequestV1;
use clinical_core::clinical::clinical_diagnosis_v0::ClinicalDiagnosisV0;
use clinical_core::clinical::clinical_observation_v1::ClinicalObservationV1;
use clinical_core::clinical::encounter_id::EncounterId;
use clinical_core::clinical::observation_code::ObservationCode;
use clinical_core::clinical::vital_sign_code::VitalSignCode;
use clinic_core::patient::patient_id::PatientId;
use clinic_core::scheduling::practitioner_id::PractitionerId;
use serde::Deserialize;
use showcase_core::clinical as clinical_core_logic;
use sqlx::Row;
use uuid::Uuid;

use crate::http::{self, ApiError, JsonBody};
use crate::AppState;

const ENCOUNTER_COLUMNS: &str = "encounter_id, patient_id, practitioner_id, appointment_id, status, \
     started_at, ended_at, expected_duration, reason_code, diagnoses, created_at, updated_at";

pub fn clinical_routes() -> Router<AppState> {
    Router::new()
        .route("/api/encounters", post(create_encounter))
        .route("/api/encounters/{id}", patch(update_encounter))
        .route("/api/encounters/{id}/observations", post(create_observation))
}

// --- status + time helpers -----------------------------------------------------

fn parse_uuid(value: &str, label: &str) -> Result<Uuid, ApiError> {
    Uuid::parse_str(value)
        .map_err(|err| ApiError::bad_request(format!("invalid {label} '{value}': {err}")))
}

fn parse_reply_status(value: &str) -> Result<ClinicalEncounterReplyV1Status, ApiError> {
    serde_json::from_str::<ClinicalEncounterReplyV1Status>(&format!("\"{value}\""))
        .map_err(|err| ApiError::internal(format!("invalid status '{value}' in encounter_db: {err}")))
}

fn row_to_reply(row: &sqlx::postgres::PgRow) -> Result<ClinicalEncounterReplyV1, ApiError> {
    let encounter_id: String = row
        .try_get("encounter_id")
        .map_err(|err| ApiError::internal(format!("decoding encounter_id: {err}")))?;
    let patient_id: String = row
        .try_get("patient_id")
        .map_err(|err| ApiError::internal(format!("decoding patient_id: {err}")))?;
    let practitioner_id: String = row
        .try_get("practitioner_id")
        .map_err(|err| ApiError::internal(format!("decoding practitioner_id: {err}")))?;
    let appointment_id: Option<String> = row
        .try_get("appointment_id")
        .map_err(|err| ApiError::internal(format!("decoding appointment_id: {err}")))?;
    let status: String = row
        .try_get("status")
        .map_err(|err| ApiError::internal(format!("decoding status: {err}")))?;
    let started_at: DateTime<Utc> = row
        .try_get("started_at")
        .map_err(|err| ApiError::internal(format!("decoding started_at: {err}")))?;
    let ended_at: Option<DateTime<Utc>> = row
        .try_get("ended_at")
        .map_err(|err| ApiError::internal(format!("decoding ended_at: {err}")))?;
    let expected_duration: Option<String> = row
        .try_get("expected_duration")
        .map_err(|err| ApiError::internal(format!("decoding expected_duration: {err}")))?;
    let reason_code: Option<String> = row
        .try_get("reason_code")
        .map_err(|err| ApiError::internal(format!("decoding reason_code: {err}")))?;
    let diagnoses: Option<Vec<sqlx::types::Json<ClinicalDiagnosisV0>>> = row
        .try_get("diagnoses")
        .map_err(|err| ApiError::internal(format!("decoding diagnoses: {err}")))?;
    let created_at: DateTime<Utc> = row
        .try_get("created_at")
        .map_err(|err| ApiError::internal(format!("decoding created_at: {err}")))?;
    let updated_at: Option<DateTime<Utc>> = row
        .try_get("updated_at")
        .map_err(|err| ApiError::internal(format!("decoding updated_at: {err}")))?;

    Ok(ClinicalEncounterReplyV1 {
        encounter_id: EncounterId(
            Uuid::from_str(&encounter_id)
                .map_err(|err| ApiError::internal(format!("encounter_id is not a uuid: {err}")))?,
        ),
        patient_id: PatientId(
            Uuid::from_str(&patient_id)
                .map_err(|err| ApiError::internal(format!("patient_id is not a uuid: {err}")))?,
        ),
        practitioner_id: PractitionerId(
            Uuid::from_str(&practitioner_id)
                .map_err(|err| ApiError::internal(format!("practitioner_id is not a uuid: {err}")))?,
        ),
        appointment_id,
        status: parse_reply_status(&status)?,
        started_at,
        ended_at,
        expected_duration: expected_duration.map(|value| http::parse_iso_duration(&value)).transpose()?,
        reason_code,
        diagnoses: diagnoses.map(|items| items.into_iter().map(|item| item.0).collect()),
        created_at,
        updated_at,
    })
}

async fn fetch_encounter(
    pool: &sqlx::PgPool,
    encounter_id: &str,
) -> Result<Option<ClinicalEncounterReplyV1>, ApiError> {
    let row = sqlx::query(&format!("SELECT {ENCOUNTER_COLUMNS} FROM encounter_db WHERE encounter_id = $1"))
        .bind(encounter_id)
        .fetch_optional(pool)
        .await
        .map_err(|err| ApiError::internal(format!("encounter lookup failed: {err}")))?;
    row.as_ref().map(row_to_reply).transpose()
}

// --- handlers ----------------------------------------------------------------------

async fn create_encounter(
    State(state): State<AppState>,
    JsonBody(request): JsonBody<ClinicalEncounterRequestV1>,
) -> Result<(StatusCode, Json<ClinicalEncounterReplyV1>), ApiError> {
    parse_uuid(&request.patient_id.to_string(), "patient id")?;
    let practitioner_id = request.practitioner_id.to_string();
    let encounter_id = request.encounter_id.to_string();

    let created_at = http::utc_now();
    let db_row = clinical_core_logic::request_to_db(&request, created_at);

    let insert = sqlx::query(
        "INSERT INTO encounter_db (encounter_id, patient_id, practitioner_id, appointment_id, status, \
         started_at, ended_at, expected_duration, reason_code, diagnoses, created_at, updated_at) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) \
         ON CONFLICT (encounter_id) DO NOTHING",
    )
    .bind(&encounter_id)
    .bind(&db_row.patient_id.to_string())
    .bind(&practitioner_id)
    .bind(&db_row.appointment_id)
    .bind(clinical_core_logic::db_status_name(&db_row.status))
    .bind(db_row.started_at)
    .bind(db_row.ended_at)
    .bind(db_row.expected_duration.map(|duration| duration.to_string()))
    .bind(&db_row.reason_code)
    .bind(db_row.diagnoses.as_ref().map(|items| items.iter().map(sqlx::types::Json).collect::<Vec<_>>()))
    .bind(db_row.created_at)
    .bind(None::<DateTime<Utc>>)
    .execute(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("encounter insert failed: {err}")))?;

    if insert.rows_affected() != 1 {
        return Err(ApiError::conflict(format!("encounter {encounter_id} already exists")));
    }

    Ok((StatusCode::CREATED, Json(clinical_core_logic::db_to_reply(db_row))))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
pub struct EncounterUpdateRequest {
    pub status: String,
    pub ended_at: Option<String>,
}

async fn update_encounter(
    State(state): State<AppState>,
    Path(id): Path<String>,
    JsonBody(request): JsonBody<EncounterUpdateRequest>,
) -> Result<Json<ClinicalEncounterReplyV1>, ApiError> {
    parse_uuid(&id, "encounter id")?;

    let current = fetch_encounter(&state.pool, &id)
        .await?
        .ok_or_else(|| ApiError::not_found(format!("encounter {id} not found")))?;
    if current.status == ClinicalEncounterReplyV1Status::Cancelled {
        return Err(ApiError::conflict(format!("encounter {id} is cancelled")));
    }

    let status = match request.status.as_str() {
        "in_progress" => ClinicalEncounterDbV1Status::InProgress,
        "completed" => ClinicalEncounterDbV1Status::Completed,
        "cancelled" => ClinicalEncounterDbV1Status::Cancelled,
        other => return Err(ApiError::bad_request(format!("invalid status '{other}'"))),
    };
    let ended_at = match &request.ended_at {
        Some(value) => Some(
            chrono::DateTime::parse_from_rfc3339(value)
                .map(|dt| dt.with_timezone(&Utc))
                .map_err(|err| ApiError::bad_request(format!("invalid ended_at '{value}': {err}")))?,
        ),
        None if status == ClinicalEncounterDbV1Status::Completed => Some(http::utc_now()),
        None => current.ended_at,
    };
    let updated_at = http::utc_now();

    let update = sqlx::query(
        "UPDATE encounter_db SET status = $1, ended_at = $2, updated_at = $3 WHERE encounter_id = $4",
    )
    .bind(clinical_core_logic::db_status_name(&status))
    .bind(ended_at)
    .bind(updated_at)
    .bind(&id)
    .execute(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("encounter update failed: {err}")))?;

    if update.rows_affected() != 1 {
        return Err(ApiError::not_found(format!("encounter {id} not found")));
    }

    let refreshed = fetch_encounter(&state.pool, &id)
        .await?
        .ok_or_else(|| ApiError::internal(format!("encounter {id} disappeared after update")))?;
    Ok(Json(refreshed))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
pub struct ObservationBody {
    pub observation_id: Option<String>,
    pub code: String,
    pub temperature_celsius: Option<f64>,
    pub weight_kg: Option<String>,
    pub blood_pressure_systolic: Option<u8>,
    pub blood_pressure_diastolic: Option<u8>,
    pub pulse_bpm: Option<u8>,
    pub is_abnormal: Option<bool>,
    pub device_id: Option<String>,
    pub metadata: Option<serde_json::Value>,
    pub recorded_at: Option<String>,
}

async fn create_observation(
    State(state): State<AppState>,
    Path(id): Path<String>,
    JsonBody(body): JsonBody<ObservationBody>,
) -> Result<(StatusCode, Json<ClinicalObservationV1>), ApiError> {
    parse_uuid(&id, "encounter id")?;

    // The encounter must exist (generate a real FK-style integrity check).
    let exists = sqlx::query_scalar::<_, bool>(
        "SELECT EXISTS(SELECT 1 FROM encounter_db WHERE encounter_id = $1)",
    )
    .bind(&id)
    .fetch_one(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("encounter existence check failed: {err}")))?;
    if !exists {
        return Err(ApiError::not_found(format!("encounter {id} not found")));
    }

    let observation_id = match body.observation_id {
        Some(value) => parse_uuid(&value, "observation id")?,
        None => Uuid::new_v4(),
    };
    let device_id = match &body.device_id {
        Some(value) => Some(parse_uuid(value, "device id")?),
        None => None,
    };
    let recorded_at = match &body.recorded_at {
        Some(value) => chrono::DateTime::parse_from_rfc3339(value)
            .map(|dt| dt.with_timezone(&Utc))
            .map_err(|err| ApiError::bad_request(format!("invalid recorded_at '{value}': {err}")))?,
        None => http::utc_now(),
    };

    let observation = ClinicalObservationV1 {
        observation_id,
        encounter_id: id.clone(),
        code: ObservationCode(VitalSignCode(body.code.clone())),
        is_abnormal: body.is_abnormal.unwrap_or(false),
        recorded_at,
        temperature_celsius: body.temperature_celsius,
        weight_kg: body.weight_kg.clone(),
        blood_pressure_systolic: body.blood_pressure_systolic,
        blood_pressure_diastolic: body.blood_pressure_diastolic,
        pulse_bpm: body.pulse_bpm,
        device_id,
        device_signature: None,
        raw_device_payload: None,
        raw_device_reading: None,
        metadata: body.metadata.clone().map(serde_json::from_value).transpose().map_err(
            |err| ApiError::bad_request(format!("invalid metadata: {err}")),
        )?,
    };

    let insert = sqlx::query(
        "INSERT INTO observation_db (observation_id, encounter_id, code, is_abnormal, recorded_at, \
         temperature_celsius, weight_kg, blood_pressure_systolic, blood_pressure_diastolic, pulse_bpm, \
         device_id, metadata) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb) \
         ON CONFLICT (observation_id) DO NOTHING",
    )
    .bind(observation.observation_id.to_string())
    .bind(&observation.encounter_id)
    .bind(&observation.code.0.0)
    .bind(observation.is_abnormal)
    .bind(observation.recorded_at)
    .bind(observation.temperature_celsius)
    .bind(&observation.weight_kg)
    .bind(observation.blood_pressure_systolic.map(|value| value as i32))
    .bind(observation.blood_pressure_diastolic.map(|value| value as i32))
    .bind(observation.pulse_bpm.map(|value| value as i32))
    .bind(observation.device_id.map(|id| id.to_string()))
    .bind(observation.metadata.as_ref().map(|m| serde_json::to_string(m).unwrap_or_default()))
    .execute(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("observation insert failed: {err}")))?;

    if insert.rows_affected() != 1 {
        return Err(ApiError::conflict(format!(
            "observation {} already exists",
            observation.observation_id
        )));
    }

    Ok((StatusCode::CREATED, Json(observation)))
}
