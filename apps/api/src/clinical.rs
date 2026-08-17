//! Clinical API (IMPLEMENTATION_PLAN.md Task 9.4).
//!
//! Uses the generated Encounter request/reply types at the API boundary and
//! persists to the generated `encounter_db` table (its generated DDL carries a
//! `FOREIGN KEY (appointment_id) REFERENCES appointment (...)` clause broken by
//! UPSTREAM_FINDINGS.md #27, so applying it to a dev database currently
//! requires dropping that clause by hand - not a second handwritten schema per
//! SPEC.md). Observation is an event-only model with no generated table at
//! all, so this API persists observations to a hand-written `observation_db`
//! table instead. EncounterId/PatientId/PractitionerId are client-supplied
//! (the generated request projection only excludes `@server` fields);
//! createdAt/updatedAt are server-generated.

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::post;
use axum::{Json, Router};
use chrono::{DateTime, Utc};
use clinical_core::clinical::clinical_encounter_db_v1::{
    ClinicalEncounterDbV1, ClinicalEncounterDbV1Status,
};
use clinical_core::clinical::clinical_encounter_reply_v1::{
    ClinicalEncounterReplyV1, ClinicalEncounterReplyV1Status,
};
use clinical_core::clinical::clinical_encounter_request_v1::{
    ClinicalEncounterRequestV1, ClinicalEncounterRequestV1Status,
};
use clinical_core::clinical::clinical_observation_v1::ClinicalObservationV1;
use clinical_core::clinical::observation_code::ObservationCode;
use clinical_core::clinical::vital_sign_code::VitalSignCode;
use serde::Deserialize;
use uuid::Uuid;

use crate::http::{self, ApiError, JsonBody};
use crate::AppState;

pub fn clinical_routes() -> Router<AppState> {
    Router::new()
        .route("/api/encounters", post(create_encounter))
        .route("/api/encounters/{id}/observations", post(create_observation))
}

// --- status + time helpers -----------------------------------------------------

fn request_status_to_db(status: ClinicalEncounterRequestV1Status) -> ClinicalEncounterDbV1Status {
    match status {
        ClinicalEncounterRequestV1Status::InProgress => ClinicalEncounterDbV1Status::InProgress,
        ClinicalEncounterRequestV1Status::Completed => ClinicalEncounterDbV1Status::Completed,
        ClinicalEncounterRequestV1Status::Cancelled => ClinicalEncounterDbV1Status::Cancelled,
    }
}

fn db_status_to_reply(status: ClinicalEncounterDbV1Status) -> ClinicalEncounterReplyV1Status {
    match status {
        ClinicalEncounterDbV1Status::InProgress => ClinicalEncounterReplyV1Status::InProgress,
        ClinicalEncounterDbV1Status::Completed => ClinicalEncounterReplyV1Status::Completed,
        ClinicalEncounterDbV1Status::Cancelled => ClinicalEncounterReplyV1Status::Cancelled,
    }
}

fn parse_uuid(value: &str, label: &str) -> Result<Uuid, ApiError> {
    Uuid::parse_str(value)
        .map_err(|err| ApiError::bad_request(format!("invalid {label} '{value}': {err}")))
}

// --- mapping helpers ------------------------------------------------------------

fn request_to_db(
    request: &ClinicalEncounterRequestV1,
    created_at: DateTime<Utc>,
) -> ClinicalEncounterDbV1 {
    ClinicalEncounterDbV1 {
        encounter_id: request.encounter_id,
        patient_id: request.patient_id.clone(),
        practitioner_id: request.practitioner_id,
        appointment_id: request.appointment_id.clone(),
        status: request_status_to_db(request.status.clone()),
        started_at: request.started_at,
        ended_at: request.ended_at,
        expected_duration: request.expected_duration,
        reason_code: request.reason_code.clone(),
        diagnoses: request.diagnoses.clone(),
        created_at,
        updated_at: None,
    }
}

fn db_to_reply(db: ClinicalEncounterDbV1) -> ClinicalEncounterReplyV1 {
    ClinicalEncounterReplyV1 {
        encounter_id: db.encounter_id,
        patient_id: db.patient_id,
        practitioner_id: db.practitioner_id,
        appointment_id: db.appointment_id,
        status: db_status_to_reply(db.status),
        started_at: db.started_at,
        ended_at: db.ended_at,
        expected_duration: db.expected_duration,
        reason_code: db.reason_code,
        diagnoses: db.diagnoses,
        created_at: db.created_at,
        updated_at: db.updated_at,
    }
}

fn db_status_to_str(status: &ClinicalEncounterDbV1Status) -> &'static str {
    match status {
        ClinicalEncounterDbV1Status::InProgress => "in_progress",
        ClinicalEncounterDbV1Status::Completed => "completed",
        ClinicalEncounterDbV1Status::Cancelled => "cancelled",
    }
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
    let db_row = request_to_db(&request, created_at);

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
    .bind(db_status_to_str(&db_row.status))
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

    Ok((StatusCode::CREATED, Json(db_to_reply(db_row))))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
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
