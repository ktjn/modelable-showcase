//! Shared HTTP concerns for the showcase API: the JSON body extractor with a
//! deterministic 400 rejection, the API error type, and small helpers.

use axum::body::Bytes;
use axum::extract::{FromRequest, Request};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use chrono::{SecondsFormat, Utc};

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

pub fn utc_now_rfc3339() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true)
}

pub fn json<T: serde::Serialize>(value: &T) -> Result<String, ApiError> {
    serde_json::to_string(value)
        .map_err(|err| ApiError::internal(format!("serialization failed: {err}")))
}

pub fn format_rfc3339(value: chrono::DateTime<chrono::Utc>) -> String {
    value.to_rfc3339_opts(SecondsFormat::Secs, true)
}

pub fn parse_timestamp(value: &str) -> Result<chrono::DateTime<chrono::Utc>, ApiError> {
    chrono::DateTime::parse_from_rfc3339(value)
        .map(|dt| dt.with_timezone(&chrono::Utc))
        .map_err(|err| ApiError::bad_request(format!("invalid timestamp '{value}': {err}")))
}