//! Scheduling API (IMPLEMENTATION_PLAN.md Task 9.3).
//!
//! Uses the generated Appointment request/reply types at the API boundaries and
//! persists to the generated `appointment_db` table. Per the model,
//! `appointmentId`, `status`, and the slot's `start`/`end` times are
//! client-supplied (the generated request projection only excludes `@server`
//! fields), while `createdAt`/`updatedAt` are server-generated. The generated
//! DDL declares `appointment_id` as `PRIMARY KEY`, so duplicate booking is
//! rejected atomically with `INSERT ... ON CONFLICT (appointment_id) DO NOTHING`
//! returning 409.
//!
//! A simple no-overlap validation (per the task spec) rejects bookings that
//! overlap another non-cancelled appointment for the same practitioner and
//! day; the query exercises the generated `appointment_db_by_practitioner_day`
//! index. Durations and slots round-trip through the generated types' ISO-8601
//! and `HH:MM:SS` serializations respectively.

use std::str::FromStr;

use axum::extract::{Path, Query, State};
use axum::http::StatusCode;
use axum::routing::{get, patch, post};
use axum::{Json, Router};
use chrono::{DateTime, NaiveDate, Utc};
use clinic_core::scheduling::appointment_id::AppointmentId;
use clinic_core::scheduling::practitioner_id::PractitionerId;
use clinic_core::scheduling::scheduling_appointment_reply_v1::{
    SchedulingAppointmentReplyV1, SchedulingAppointmentReplyV1Status,
};
use clinic_core::scheduling::scheduling_appointment_request_v1::SchedulingAppointmentRequestV1;
use clinic_core::scheduling::scheduling_time_range_v0::SchedulingTimeRangeV0;
use serde::Deserialize;
use showcase_core::scheduling as scheduling_core;
use sqlx::Row;
use uuid::Uuid;

use crate::http::{self, ApiError, JsonBody};
use crate::AppState;

const APPOINTMENT_COLUMNS: &str = "appointment_id, patient_id, practitioner_id, scheduled_date, \
     slot, buffer_duration, status, reason, notes, created_at, updated_at";

pub fn scheduling_routes() -> Router<AppState> {
    Router::new()
        .route("/api/appointments", post(create_appointment))
        .route("/api/appointments/{id}", patch(reschedule_appointment))
        .route("/api/appointments/{id}/cancel", post(cancel_appointment))
        .route("/api/schedule", get(daily_schedule))
        .route("/api/patients/{id}/appointments", get(patient_appointments))
}

fn parse_date(value: &str) -> Result<NaiveDate, ApiError> {
    NaiveDate::parse_from_str(value, "%Y-%m-%d")
        .map_err(|err| ApiError::bad_request(format!("invalid date '{value}': {err}")))
}

fn parse_uuid(value: &str, label: &str) -> Result<Uuid, ApiError> {
    Uuid::parse_str(value)
        .map_err(|err| ApiError::bad_request(format!("invalid {label} '{value}': {err}")))
}

fn row_to_reply(row: &sqlx::postgres::PgRow) -> Result<SchedulingAppointmentReplyV1, ApiError> {
    let appointment_id: String = row
        .try_get("appointment_id")
        .map_err(|err| ApiError::internal(format!("decoding appointment_id: {err}")))?;
    let patient_id: String = row
        .try_get("patient_id")
        .map_err(|err| ApiError::internal(format!("decoding patient_id: {err}")))?;
    let practitioner_id: String = row
        .try_get("practitioner_id")
        .map_err(|err| ApiError::internal(format!("decoding practitioner_id: {err}")))?;
    let scheduled_date: NaiveDate = row
        .try_get("scheduled_date")
        .map_err(|err| ApiError::internal(format!("decoding scheduled_date: {err}")))?;
    let slot: sqlx::types::Json<SchedulingTimeRangeV0> = row
        .try_get("slot")
        .map_err(|err| ApiError::internal(format!("decoding slot: {err}")))?;
    let buffer_duration: Option<String> = row
        .try_get("buffer_duration")
        .map_err(|err| ApiError::internal(format!("decoding buffer_duration: {err}")))?;
    let status: String = row
        .try_get("status")
        .map_err(|err| ApiError::internal(format!("decoding status: {err}")))?;
    let reason: Option<String> = row
        .try_get("reason")
        .map_err(|err| ApiError::internal(format!("decoding reason: {err}")))?;
    let notes: Option<String> = row
        .try_get("notes")
        .map_err(|err| ApiError::internal(format!("decoding notes: {err}")))?;
    let created_at: DateTime<Utc> = row
        .try_get("created_at")
        .map_err(|err| ApiError::internal(format!("decoding created_at: {err}")))?;
    let updated_at: Option<DateTime<Utc>> = row
        .try_get("updated_at")
        .map_err(|err| ApiError::internal(format!("decoding updated_at: {err}")))?;

    Ok(SchedulingAppointmentReplyV1 {
        appointment_id: AppointmentId(
            Uuid::from_str(&appointment_id)
                .map_err(|err| ApiError::internal(format!("appointment_id is not a uuid: {err}")))?,
        ),
        patient_id,
        practitioner_id: PractitionerId(
            Uuid::from_str(&practitioner_id)
                .map_err(|err| ApiError::internal(format!("practitioner_id is not a uuid: {err}")))?,
        ),
        scheduled_date,
        slot: slot.0,
        status: parse_reply_status(&status)?,
        created_at,
        buffer_duration: buffer_duration
            .map(|value| http::parse_iso_duration(&value))
            .transpose()?,
        reason,
        notes,
        updated_at,
    })
}

fn parse_reply_status(value: &str) -> Result<SchedulingAppointmentReplyV1Status, ApiError> {
    serde_json::from_str::<SchedulingAppointmentReplyV1Status>(&format!("\"{value}\""))
        .map_err(|err| ApiError::internal(format!("invalid status '{value}' in appointment_db: {err}")))
}

// --- shared lookups ---------------------------------------------------------------

async fn fetch_appointment(
    pool: &sqlx::PgPool,
    appointment_id: &str,
) -> Result<Option<SchedulingAppointmentReplyV1>, ApiError> {
    let row = sqlx::query(&format!(
        "SELECT {APPOINTMENT_COLUMNS} FROM appointment_db WHERE appointment_id = $1"
    ))
    .bind(appointment_id)
    .fetch_optional(pool)
    .await
    .map_err(|err| ApiError::internal(format!("appointment lookup failed: {err}")))?;
    row.as_ref()
        .map(row_to_reply)
        .transpose()
}

async fn any_overlapping(
    pool: &sqlx::PgPool,
    practitioner_id: &str,
    date: NaiveDate,
    slot: &SchedulingTimeRangeV0,
    exclude_appointment_id: Option<&str>,
) -> Result<bool, ApiError> {
    let mut sql = String::from(
        "SELECT slot FROM appointment_db WHERE practitioner_id = $1 \
         AND scheduled_date = $2 AND status <> 'cancelled'",
    );
    let mut extra: Vec<String> = vec![];
    if let Some(exclude) = exclude_appointment_id {
        extra.push(exclude.to_string());
        sql.push_str(&format!(" AND appointment_id <> ${}", extra.len() + 2));
    }

    let mut query = sqlx::query(&sql).bind(practitioner_id).bind(date);
    for value in &extra {
        query = query.bind(value);
    }
    let rows = query
        .fetch_all(pool)
        .await
        .map_err(|err| ApiError::internal(format!("overlap check failed: {err}")))?;

    for row in &rows {
        let slot_json: sqlx::types::Json<SchedulingTimeRangeV0> = row
            .try_get("slot")
            .map_err(|err| ApiError::internal(format!("decoding slot: {err}")))?;
        if scheduling_core::slots_overlap(&slot_json.0, slot)? {
            return Ok(true);
        }
    }
    Ok(false)
}

// --- handlers ----------------------------------------------------------------------

async fn create_appointment(
    State(state): State<AppState>,
    JsonBody(request): JsonBody<SchedulingAppointmentRequestV1>,
) -> Result<(StatusCode, Json<SchedulingAppointmentReplyV1>), ApiError> {
    scheduling_core::validate_slot(&request.slot)?;
    parse_uuid(&request.patient_id, "patient id")?;
    let practitioner_id = request.practitioner_id.to_string();
    let appointment_id = request.appointment_id.to_string();

    if any_overlapping(
        &state.pool,
        &practitioner_id,
        request.scheduled_date,
        &request.slot,
        None,
    )
    .await?
    {
        return Err(ApiError::conflict(format!(
            "appointment overlaps an existing {practitioner_id} appointment on {}",
            request.scheduled_date
        )));
    }

    let created_at = http::utc_now();
    let db_row = scheduling_core::request_to_db(&request, created_at);

    // appointment_id is the generated PK; atomic duplicate detection.
    let insert = sqlx::query(
        "INSERT INTO appointment_db (appointment_id, patient_id, practitioner_id, scheduled_date, \
         slot, buffer_duration, status, reason, notes, created_at, updated_at) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) \
         ON CONFLICT (appointment_id) DO NOTHING",
    )
    .bind(db_row.appointment_id.to_string())
    .bind(&db_row.patient_id)
    .bind(db_row.practitioner_id.to_string())
    .bind(db_row.scheduled_date)
    .bind(sqlx::types::Json(&db_row.slot))
    .bind(db_row.buffer_duration.map(|duration| duration.to_string()))
    .bind(scheduling_core::db_status_name(&db_row.status))
    .bind(&db_row.reason)
    .bind(&db_row.notes)
    .bind(db_row.created_at)
    .bind(None::<DateTime<Utc>>)
    .execute(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("appointment insert failed: {err}")))?;

    if insert.rows_affected() != 1 {
        return Err(ApiError::conflict(format!("appointment {appointment_id} already exists")));
    }

    crate::analytics::record_appointment_event(
        &state.clickhouse,
        &appointment_id,
        &db_row.patient_id,
        &practitioner_id,
        db_row.scheduled_date,
        &serde_json::to_string(&db_row.slot).unwrap_or_default(),
        scheduling_core::db_status_name(&db_row.status),
        db_row.created_at,
    )
    .await;

    Ok((StatusCode::CREATED, Json(scheduling_core::db_to_reply(db_row))))
}

#[derive(Deserialize, Default)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
pub struct RescheduleRequest {
    pub scheduled_date: Option<String>,
    pub slot: Option<SchedulingTimeRangeV0>,
    pub buffer_duration: Option<String>,
    pub reason: Option<String>,
    pub notes: Option<String>,
}

async fn reschedule_appointment(
    State(state): State<AppState>,
    Path(id): Path<String>,
    JsonBody(request): JsonBody<RescheduleRequest>,
) -> Result<Json<SchedulingAppointmentReplyV1>, ApiError> {
    parse_uuid(&id, "appointment id")?;

    let current = fetch_appointment(&state.pool, &id)
        .await?
        .ok_or_else(|| ApiError::not_found(format!("appointment {id} not found")))?;
    if current.status == SchedulingAppointmentReplyV1Status::Cancelled {
        return Err(ApiError::conflict(format!("appointment {id} is cancelled")));
    }

    let scheduled_date = match &request.scheduled_date {
        Some(value) => parse_date(value)?,
        None => current.scheduled_date,
    };
    let slot = request.slot.clone().unwrap_or_else(|| current.slot.clone());
    scheduling_core::validate_slot(&slot)?;

    if any_overlapping(
        &state.pool,
        &current.practitioner_id.to_string(),
        scheduled_date,
        &slot,
        Some(&id),
    )
    .await?
    {
        return Err(ApiError::conflict(format!(
            "reschedule overlaps an existing appointment for {} on {scheduled_date}",
            *current.practitioner_id
        )));
    }

    let buffer_duration = match &request.buffer_duration {
        Some(value) => Some(http::parse_iso_duration(value)?),
        None => current.buffer_duration,
    };
    let reason = request.reason.clone().or(current.reason.clone());
    let notes = request.notes.clone().or(current.notes.clone());
    let updated_at = http::utc_now();

    let update = sqlx::query(
        "UPDATE appointment_db SET scheduled_date = $1, slot = $2, buffer_duration = \
         $3, reason = $4, notes = $5, updated_at = $6 \
         WHERE appointment_id = $7",
    )
    .bind(scheduled_date)
    .bind(sqlx::types::Json(&slot))
    .bind(buffer_duration.map(|duration| duration.to_string()))
    .bind(reason.clone())
    .bind(notes.clone())
    .bind(updated_at)
    .bind(&id)
    .execute(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("appointment update failed: {err}")))?;

    if update.rows_affected() != 1 {
        return Err(ApiError::not_found(format!("appointment {id} not found")));
    }

    let refreshed = fetch_appointment(&state.pool, &id)
        .await?
        .ok_or_else(|| ApiError::internal(format!("appointment {id} disappeared after update")))?;
    Ok(Json(refreshed))
}

#[derive(Deserialize, Default)]
#[serde(deny_unknown_fields)]
pub struct CancelRequest {
    pub reason: Option<String>,
}

async fn cancel_appointment(
    State(state): State<AppState>,
    Path(id): Path<String>,
    JsonBody(request): JsonBody<CancelRequest>,
) -> Result<Json<SchedulingAppointmentReplyV1>, ApiError> {
    parse_uuid(&id, "appointment id")?;

    let current = fetch_appointment(&state.pool, &id)
        .await?
        .ok_or_else(|| ApiError::not_found(format!("appointment {id} not found")))?;
    if current.status == SchedulingAppointmentReplyV1Status::Cancelled {
        return Err(ApiError::conflict(format!("appointment {id} is already cancelled")));
    }

    let updated_at = http::utc_now();
    let reason = request.reason.clone().or(current.reason.clone());

    let update = sqlx::query(
        "UPDATE appointment_db SET status = 'cancelled', reason = $1, updated_at = $2 \
         WHERE appointment_id = $3",
    )
    .bind(reason.clone())
    .bind(updated_at)
    .bind(&id)
    .execute(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("appointment cancel failed: {err}")))?;

    if update.rows_affected() != 1 {
        return Err(ApiError::not_found(format!("appointment {id} not found")));
    }

    let refreshed = fetch_appointment(&state.pool, &id)
        .await?
        .ok_or_else(|| ApiError::internal(format!("appointment {id} disappeared after cancel")))?;
    Ok(Json(refreshed))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ScheduleQuery {
    pub date: String,
    pub practitioner: Option<String>,
}

async fn daily_schedule(
    State(state): State<AppState>,
    Query(query): Query<ScheduleQuery>,
) -> Result<Json<Vec<SchedulingAppointmentReplyV1>>, ApiError> {
    parse_date(&query.date)?;
    if let Some(practitioner) = &query.practitioner {
        parse_uuid(practitioner, "practitioner id")?;
    }

    let mut sql = format!(
        "SELECT {APPOINTMENT_COLUMNS} FROM appointment_db WHERE scheduled_date = $1"
    );
    let mut extra: Vec<String> = vec![];
    if let Some(practitioner) = &query.practitioner {
        extra.push(practitioner.clone());
        sql.push_str(&format!(" AND practitioner_id = ${}", extra.len() + 1));
    }
    sql.push_str(" ORDER BY (slot ->> 'start'), appointment_id");

    let scheduled_date = parse_date(&query.date)?;
    let mut q = sqlx::query(&sql).bind(scheduled_date);
    for value in &extra {
        q = q.bind(value);
    }
    let rows = q
        .fetch_all(&state.pool)
        .await
        .map_err(|err| ApiError::internal(format!("daily schedule query failed: {err}")))?;

    let replies = rows
        .iter()
        .map(row_to_reply)
        .collect::<Result<Vec<_>, _>>()?;
    Ok(Json(replies))
}

async fn patient_appointments(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<Vec<SchedulingAppointmentReplyV1>>, ApiError> {
    parse_uuid(&id, "patient id")?;

    let rows = sqlx::query(&format!(
        "SELECT {APPOINTMENT_COLUMNS} FROM appointment_db WHERE patient_id = $1 \
         ORDER BY scheduled_date, (slot ->> 'start'), appointment_id"
    ))
    .bind(&id)
    .fetch_all(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("patient appointment lookup failed: {err}")))?;

    let replies = rows
        .iter()
        .map(row_to_reply)
        .collect::<Result<Vec<_>, _>>()?;
    Ok(Json(replies))
}
