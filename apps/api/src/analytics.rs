//! Analytics write/query path (IMPLEMENTATION_PLAN.md Task 9.5).
//!
//! Application code owns synchronization explicitly (no Modelable
//! subscriptions/materialisation): `scheduling::create_appointment`,
//! `billing::create_invoice`, and `billing::create_payment` call the
//! `record_*_event` helpers below immediately after their PostgreSQL insert
//! commits. Writes to ClickHouse are best-effort - a ClickHouse outage must
//! not fail the PostgreSQL-backed request that already succeeded, so failures
//! are logged and swallowed here rather than surfaced as an `ApiError`.
//!
//! `appointment_event`/`invoice_event` are the generated `sql-clickhouse`
//! tables for those domains (SPEC.md forbids a second handwritten schema for
//! a table Modelable already generates). `payment_event` has no generated
//! table - `PaymentReceived` is declared as a bare `event` with no `auto
//! projections` block - so it is a hand-written table, applied to the dev
//! ClickHouse the same way `payment_db`/`observation_db` are applied to the
//! dev PostgreSQL. `Decimal(10, 2)` columns are wire-encoded as scaled `i64`
//! (cents); `DateTime64(9)` as nanosecond `i64`; `Date` as days-since-epoch
//! `u16` - see `to_ch_*` below.

use axum::extract::State;
use axum::routing::get;
use axum::{Json, Router};
use chrono::{DateTime, NaiveDate, Utc};
use clickhouse::Row;
use serde::{Deserialize, Serialize};

use crate::http::ApiError;
use crate::AppState;

pub fn analytics_routes() -> Router<AppState> {
    Router::new().route("/api/analytics/clinic", get(clinic_analytics))
}

// --- wire-format conversions ---------------------------------------------------

fn to_ch_date(date: NaiveDate) -> u16 {
    (date - NaiveDate::from_ymd_opt(1970, 1, 1).expect("valid epoch date")).num_days() as u16
}

fn to_ch_datetime(instant: DateTime<Utc>) -> i64 {
    instant.timestamp_nanos_opt().unwrap_or(0)
}

/// Parses a decimal string (as emitted by the generated contracts, e.g.
/// `"125.00"`) into an integer scaled by `10^scale`, matching how
/// `Decimal(precision, scale)` columns are wire-encoded.
fn to_ch_decimal(value: &str, scale: u32) -> Result<i64, String> {
    let (negative, unsigned) = value.strip_prefix('-').map_or((false, value), |rest| (true, rest));
    let mut parts = unsigned.splitn(2, '.');
    let int_part = parts.next().unwrap_or("0");
    let frac_part = parts.next().unwrap_or("");
    if frac_part.len() > scale as usize {
        return Err(format!("decimal '{value}' has more than {scale} fractional digits"));
    }
    let mut frac_padded = frac_part.to_string();
    while frac_padded.len() < scale as usize {
        frac_padded.push('0');
    }
    let magnitude: i64 = format!("{int_part}{frac_padded}")
        .parse()
        .map_err(|err| format!("invalid decimal '{value}': {err}"))?;
    Ok(if negative { -magnitude } else { magnitude })
}

// --- event writers ---------------------------------------------------------------

#[derive(Row, Serialize)]
struct AppointmentEventRow {
    appointment_id: String,
    patient_id: String,
    practitioner_id: String,
    scheduled_date: u16,
    slot: String,
    status: String,
    created_at: i64,
}

pub async fn record_appointment_event(
    client: &clickhouse::Client,
    appointment_id: &str,
    patient_id: &str,
    practitioner_id: &str,
    scheduled_date: NaiveDate,
    slot: &str,
    status: &str,
    created_at: DateTime<Utc>,
) {
    let row = AppointmentEventRow {
        appointment_id: appointment_id.to_string(),
        patient_id: patient_id.to_string(),
        practitioner_id: practitioner_id.to_string(),
        scheduled_date: to_ch_date(scheduled_date),
        slot: slot.to_string(),
        status: status.to_string(),
        created_at: to_ch_datetime(created_at),
    };
    if let Err(err) = write_appointment_event(client, row).await {
        tracing::error!("appointment_event analytics write failed: {err}");
    }
}

async fn write_appointment_event(
    client: &clickhouse::Client,
    row: AppointmentEventRow,
) -> clickhouse::error::Result<()> {
    let mut insert = client.insert::<AppointmentEventRow>("appointment_event").await?;
    insert.write(&row).await?;
    insert.end().await
}

#[derive(Row, Serialize)]
struct InvoiceEventRow {
    invoice_id: String,
    patient_id: String,
    subtotal: i64,
    tax: i64,
    total: i64,
    status: String,
    created_at: i64,
}

pub async fn record_invoice_event(
    client: &clickhouse::Client,
    invoice_id: &str,
    patient_id: &str,
    subtotal: &str,
    tax: &str,
    total: &str,
    status: &str,
    created_at: DateTime<Utc>,
) {
    let row = match (to_ch_decimal(subtotal, 2), to_ch_decimal(tax, 2), to_ch_decimal(total, 2)) {
        (Ok(subtotal), Ok(tax), Ok(total)) => InvoiceEventRow {
            invoice_id: invoice_id.to_string(),
            patient_id: patient_id.to_string(),
            subtotal,
            tax,
            total,
            status: status.to_string(),
            created_at: to_ch_datetime(created_at),
        },
        (subtotal, tax, total) => {
            let reason = subtotal.err().or(tax.err()).or(total.err()).unwrap_or_default();
            tracing::error!("invoice_event analytics write skipped: invalid decimal: {reason}");
            return;
        }
    };
    if let Err(err) = write_invoice_event(client, row).await {
        tracing::error!("invoice_event analytics write failed: {err}");
    }
}

async fn write_invoice_event(client: &clickhouse::Client, row: InvoiceEventRow) -> clickhouse::error::Result<()> {
    let mut insert = client.insert::<InvoiceEventRow>("invoice_event").await?;
    insert.write(&row).await?;
    insert.end().await
}

#[derive(Row, Serialize)]
struct PaymentEventRow {
    payment_id: String,
    invoice_id: String,
    amount: i64,
    method: String,
    received_at: i64,
}

pub async fn record_payment_event(
    client: &clickhouse::Client,
    payment_id: &str,
    invoice_id: &str,
    amount: &str,
    method: &str,
    received_at: DateTime<Utc>,
) {
    let row = match to_ch_decimal(amount, 2) {
        Ok(amount) => PaymentEventRow {
            payment_id: payment_id.to_string(),
            invoice_id: invoice_id.to_string(),
            amount,
            method: method.to_string(),
            received_at: to_ch_datetime(received_at),
        },
        Err(err) => {
            tracing::error!("payment_event analytics write skipped: {err}");
            return;
        }
    };
    if let Err(err) = write_payment_event(client, row).await {
        tracing::error!("payment_event analytics write failed: {err}");
    }
}

async fn write_payment_event(client: &clickhouse::Client, row: PaymentEventRow) -> clickhouse::error::Result<()> {
    let mut insert = client.insert::<PaymentEventRow>("payment_event").await?;
    insert.write(&row).await?;
    insert.end().await
}

// --- GET /api/analytics/clinic -----------------------------------------------------

#[derive(Row, Deserialize)]
struct AppointmentsPerDayRow {
    day: String,
    appointment_count: u64,
}

#[derive(Row, Deserialize)]
struct PractitionerAggregateRow {
    practitioner_id: String,
    appointment_count: u64,
}

#[derive(Row, Deserialize)]
struct TotalRow {
    total: String,
}

/// `toString(Decimal)` strips trailing zeros (`"125"`, not `"125.00"`), so the
/// sum is re-derived as an integer cent count and formatted by hand to keep
/// the fixed 2-decimal-place string the generated contracts use elsewhere.
/// `column`/`table` are always internal literals, never request input.
fn decimal_total_query(column: &str, table: &str) -> String {
    format!(
        "SELECT concat(toString(intDiv(cents, 100)), '.', leftPad(toString(cents % 100), 2, '0')) AS total \
         FROM (SELECT toInt64(round(coalesce(sum({column}), 0) * 100)) AS cents FROM {table})"
    )
}

#[derive(Serialize)]
pub struct AppointmentsPerDay {
    pub day: String,
    pub appointment_count: u64,
}

#[derive(Serialize)]
pub struct PractitionerAppointmentCount {
    pub practitioner_id: String,
    pub appointment_count: u64,
}

#[derive(Serialize)]
pub struct ClinicAnalytics {
    pub appointments_per_day: Vec<AppointmentsPerDay>,
    pub billed_total: String,
    pub paid_total: String,
    pub practitioner_appointment_counts: Vec<PractitionerAppointmentCount>,
}

async fn clinic_analytics(State(state): State<AppState>) -> Result<Json<ClinicAnalytics>, ApiError> {
    let appointments_per_day: Vec<AppointmentsPerDayRow> = state
        .clickhouse
        .query(
            "SELECT toString(scheduled_date) AS day, count() AS appointment_count \
             FROM appointment_event GROUP BY day ORDER BY day",
        )
        .fetch_all()
        .await
        .map_err(|err| ApiError::internal(format!("appointments-per-day query failed: {err}")))?;

    let practitioner_appointment_counts: Vec<PractitionerAggregateRow> = state
        .clickhouse
        .query(
            "SELECT practitioner_id, count() AS appointment_count FROM appointment_event \
             GROUP BY practitioner_id ORDER BY appointment_count DESC, practitioner_id",
        )
        .fetch_all()
        .await
        .map_err(|err| ApiError::internal(format!("practitioner aggregate query failed: {err}")))?;

    let billed_total = state
        .clickhouse
        .query(&decimal_total_query("total", "invoice_event"))
        .fetch_one::<TotalRow>()
        .await
        .map_err(|err| ApiError::internal(format!("billed total query failed: {err}")))?
        .total;

    let paid_total = state
        .clickhouse
        .query(&decimal_total_query("amount", "payment_event"))
        .fetch_one::<TotalRow>()
        .await
        .map_err(|err| ApiError::internal(format!("paid total query failed: {err}")))?
        .total;

    Ok(Json(ClinicAnalytics {
        appointments_per_day: appointments_per_day
            .into_iter()
            .map(|row| AppointmentsPerDay { day: row.day, appointment_count: row.appointment_count })
            .collect(),
        billed_total,
        paid_total,
        practitioner_appointment_counts: practitioner_appointment_counts
            .into_iter()
            .map(|row| PractitionerAppointmentCount {
                practitioner_id: row.practitioner_id,
                appointment_count: row.appointment_count,
            })
            .collect(),
    }))
}
