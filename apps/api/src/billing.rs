//! Billing API (IMPLEMENTATION_PLAN.md Task 9.4).
//!
//! Uses the generated Invoice request/reply types at the API boundary and
//! persists to the generated `invoice_db` table, including its foreign key to
//! `encounter_db`. PaymentReceived is an event-only model with no generated table at
//! all, so this API persists payments to a hand-written `payment_db` table
//! instead. InvoiceId/PatientId are client-supplied; createdAt/updatedAt are
//! server-generated. Decimal fields (subtotal/tax/total, line
//! unitPrice/lineTotal) are emitted as strings by the generated contracts.

use std::str::FromStr;

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::post;
use axum::{Json, Router};
use chrono::{DateTime, Utc};
use billing_core::billing::billing_invoice_reply_v2::BillingInvoiceReplyV2;
use billing_core::billing::billing_invoice_request_v2::BillingInvoiceRequestV2;
use billing_core::billing::billing_payment_received_v1::{
    BillingPaymentReceivedV1, BillingPaymentReceivedV1Method,
};
use billing_core::billing::invoice_id::InvoiceId;
use serde::Deserialize;
use showcase_core::billing as billing_core_logic;
use uuid::Uuid;

use crate::http::{self, ApiError, JsonBody};
use crate::AppState;

pub fn billing_routes() -> Router<AppState> {
    Router::new()
        .route("/api/invoices", post(create_invoice))
        .route("/api/invoices/{id}/payments", post(create_payment))
}

fn parse_uuid(value: &str, label: &str) -> Result<Uuid, ApiError> {
    Uuid::parse_str(value)
        .map_err(|err| ApiError::bad_request(format!("invalid {label} '{value}': {err}")))
}

// --- handlers ------------------------------------------------------------------------

async fn create_invoice(
    State(state): State<AppState>,
    JsonBody(request): JsonBody<BillingInvoiceRequestV2>,
) -> Result<(StatusCode, Json<BillingInvoiceReplyV2>), ApiError> {
    parse_uuid(&request.patient_id.to_string(), "patient id")?;
    let invoice_id = request.invoice_id.to_string();

    billing_core_logic::validate_invoice(&request)?;
    let created_at = http::utc_now();
    let db_row = billing_core_logic::request_to_db(&request, created_at);

    let insert = sqlx::query(
        "INSERT INTO invoice_db (invoice_id, patient_id, encounter_id, lines, subtotal, tax, total, \
         currency, billing_period, status, issued_at, due_date, created_at, updated_at) \
         VALUES ($1, $2, $3, $4, $5::numeric, $6::numeric, $7::numeric, $8, $9, $10, $11, $12, $13, $14) \
         ON CONFLICT (invoice_id) DO NOTHING",
    )
    .bind(&invoice_id)
    .bind(&db_row.patient_id.to_string())
    .bind(&db_row.encounter_id)
    .bind(db_row.lines.iter().map(sqlx::types::Json).collect::<Vec<_>>())
    .bind(&db_row.subtotal)
    .bind(&db_row.tax)
    .bind(&db_row.total)
    .bind(&db_row.currency)
    .bind(&db_row.billing_period)
    .bind(billing_core_logic::db_status_name(&db_row.status))
    .bind(db_row.issued_at)
    .bind(db_row.due_date)
    .bind(db_row.created_at)
    .bind(None::<DateTime<Utc>>)
    .execute(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("invoice insert failed: {err}")))?;

    if insert.rows_affected() != 1 {
        return Err(ApiError::conflict(format!("invoice {invoice_id} already exists")));
    }

    crate::analytics::record_invoice_event(
        &state.clickhouse,
        &invoice_id,
        &db_row.patient_id.to_string(),
        &db_row.subtotal,
        &db_row.tax,
        &db_row.total,
        billing_core_logic::db_status_name(&db_row.status),
        db_row.created_at,
    )
    .await;

    Ok((StatusCode::CREATED, Json(billing_core_logic::db_to_reply(db_row))))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields, rename_all = "camelCase")]
pub struct PaymentBody {
    pub payment_id: Option<String>,
    pub amount: String,
    pub method: String,
    pub received_at: Option<String>,
}

async fn create_payment(
    State(state): State<AppState>,
    Path(id): Path<String>,
    JsonBody(body): JsonBody<PaymentBody>,
) -> Result<(StatusCode, Json<BillingPaymentReceivedV1>), ApiError> {
    parse_uuid(&id, "invoice id")?;

    let exists = sqlx::query_scalar::<_, bool>("SELECT EXISTS(SELECT 1 FROM invoice_db WHERE invoice_id = $1)")
        .bind(&id)
        .fetch_one(&state.pool)
        .await
        .map_err(|err| ApiError::internal(format!("invoice existence check failed: {err}")))?;
    if !exists {
        return Err(ApiError::not_found(format!("invoice {id} not found")));
    }

    let payment_id = match body.payment_id {
        Some(value) => parse_uuid(&value, "payment id")?,
        None => Uuid::new_v4(),
    };
    let received_at = match &body.received_at {
        Some(value) => chrono::DateTime::parse_from_rfc3339(value)
            .map(|dt| dt.with_timezone(&Utc))
            .map_err(|err| ApiError::bad_request(format!("invalid received_at '{value}': {err}")))?,
        None => http::utc_now(),
    };
    let method = serde_json::from_str::<BillingPaymentReceivedV1Method>(&format!("\"{}\"", body.method))
        .map_err(|err| ApiError::bad_request(format!("invalid method '{}': {err}", body.method)))?;

    let payment = BillingPaymentReceivedV1 {
        payment_id,
        invoice_id: InvoiceId(
            Uuid::from_str(&id)
                .map_err(|err| ApiError::internal(format!("invoice_id is not a uuid: {err}")))?,
        ),
        amount: body.amount.clone(),
        method,
        received_at,
    };

    let insert = sqlx::query(
        "INSERT INTO payment_db (payment_id, invoice_id, amount, method, received_at) \
         VALUES ($1, $2, $3::numeric, $4, $5) ON CONFLICT (payment_id) DO NOTHING",
    )
    .bind(payment.payment_id.to_string())
    .bind(&id)
    .bind(&payment.amount)
    .bind(billing_core_logic::payment_method_name(&payment.method))
    .bind(payment.received_at)
    .execute(&state.pool)
    .await
    .map_err(|err| ApiError::internal(format!("payment insert failed: {err}")))?;

    if insert.rows_affected() != 1 {
        return Err(ApiError::conflict(format!("payment {} already exists", payment.payment_id)));
    }

    crate::analytics::record_payment_event(
        &state.clickhouse,
        &payment.payment_id.to_string(),
        &id,
        &payment.amount,
        billing_core_logic::payment_method_name(&payment.method),
        payment.received_at,
    )
    .await;

    Ok((StatusCode::CREATED, Json(payment)))
}
