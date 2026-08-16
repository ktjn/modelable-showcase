//! Shared HTTP concerns for the showcase API: the JSON body extractor with a
//! deterministic 400 rejection, the API error type, and small helpers.

use axum::body::Bytes;
use axum::extract::{FromRequest, Request};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use chrono::{Timelike, Utc};

pub struct ApiError {
    pub status: StatusCode,
    pub message: String,
}

impl ApiError {
    pub fn bad_request(message: impl Into<String>) -> Self {
        Self { status: StatusCode::BAD_REQUEST, message: message.into() }
    }

    pub fn not_found(message: impl Into<String>) -> Self {
        Self { status: StatusCode::NOT_FOUND, message: message.into() }
    }

    pub fn conflict(message: impl Into<String>) -> Self {
        Self { status: StatusCode::CONFLICT, message: message.into() }
    }

    pub fn internal(message: impl Into<String>) -> Self {
        tracing::error!("{}", message.into());
        Self { status: StatusCode::INTERNAL_SERVER_ERROR, message: "internal server error".into() }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (self.status, Json(serde_json::json!({ "error": self.message }))).into_response()
    }
}

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

/// Current UTC instant for server-generated `createdAt`/`updatedAt`, truncated
/// to whole seconds so the value serialized in the response matches exactly
/// what is stored in (and read back from) the PostgreSQL `TIMESTAMPTZ` column.
/// (Without truncation Postgres would add microsecond/nanosecond precision that
/// breaks the create == fetch round-trip assertions.)
pub fn utc_now() -> chrono::DateTime<chrono::Utc> {
    let now = Utc::now();
    chrono::DateTime::from_naive_utc_and_offset(
        now.naive_utc().with_nanosecond(0).expect("timestamp has a nanosecond field"),
        Utc,
    )
}

/// Parse an ISO-8601 duration of the form chrono's `Duration::to_string()`
/// emits (seconds-normalized, e.g. `PT900S`, `P0D`, `-PT45S`) back into a
/// `chrono::Duration`. The generated `clinic-core` types serialize durations
/// with exactly this representation, so this is the inverse of storing
/// `duration.to_string()` in the `buffer_duration` TEXT column.
pub fn parse_iso_duration(value: &str) -> Result<chrono::Duration, ApiError> {
    let err = || ApiError::internal(format!("invalid stored duration '{value}'"));
    let (negative, body) = value
        .strip_prefix('-')
        .map_or((false, value), |rest| (true, rest));
    let body = body.strip_prefix('P').ok_or_else(err)?;
    let seconds = if body == "0D" {
        0
    } else if let Some(n) = body.strip_suffix('S').and_then(|s| s.strip_prefix('T')) {
        n.parse::<i64>().map_err(|_| err())?
    } else {
        return Err(err());
    };
    let duration = chrono::Duration::seconds(if negative { -seconds } else { seconds });
    Ok(duration)
}
