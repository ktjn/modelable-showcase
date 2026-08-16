//! Task 9.3 integration tests: the generated Scheduling API against the
//! showcase PostgreSQL. These skip (early-return) when the showcase DB is
//! unreachable; run `docker compose up -d` to execute them for real.

use std::time::Duration;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use axum::Router;
use clinic_core::scheduling::scheduling_appointment_reply_v1::SchedulingAppointmentReplyV1;
use clinic_core::scheduling::scheduling_appointment_request_v1::SchedulingAppointmentRequestV1;
use http_body_util::BodyExt;
use modelable_showcase_api::{app, AppState};
use serde_json::{json, Value};
use tower::ServiceExt;

const PRACTITIONER_A: &str = "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1";
const PRACTITIONER_B: &str = "b2b2b2b2-b2b2-b2b2-b2b2-b2b2b2b2b2b2";
const PATIENT: &str = "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d";

async fn db_lock() -> tokio::sync::MutexGuard<'static, ()> {
    static LOCK: tokio::sync::Mutex<()> = tokio::sync::Mutex::const_new(());
    LOCK.lock().await
}

async fn app_ready() -> Option<Router> {
    let state = AppState::default();
    let reachable = tokio::time::timeout(
        Duration::from_secs(4),
        sqlx::query_scalar::<_, i32>("SELECT 1").fetch_one(&state.pool),
    )
    .await
    .map(|result| result.is_ok())
    .unwrap_or(false);
    if !reachable {
        eprintln!(
            "SKIP: showcase PostgreSQL unreachable; run 'docker compose up -d' \
             to exercise the Scheduling API integration tests"
        );
        return None;
    }
    sqlx::query("TRUNCATE TABLE appointment_db")
        .execute(&state.pool)
        .await
        .expect("failed to TRUNCATE appointment_db");
    Some(app(state))
}

async fn call(app: &mut Router, request: Request<Body>) -> (StatusCode, Value) {
    let response = app.oneshot(request).await.unwrap();
    let status = response.status();
    let bytes = response.into_body().collect().await.unwrap().to_bytes();
    let body = serde_json::from_slice(&bytes)
        .unwrap_or_else(|_| Value::String(String::from_utf8_lossy(&bytes).into_owned()));
    (status, body)
}

async fn post_json(router: &mut Router, uri: &str, body: Value) -> (StatusCode, Value) {
    let request = Request::builder()
        .method("POST")
        .uri(uri)
        .header("content-type", "application/json")
        .body(Body::from(body.to_string()))
        .unwrap();
    call(router, request).await
}

fn booking(
    appointment_id: &str,
    practitioner_id: &str,
    date: &str,
    start: &str,
    end: &str,
    status: &str,
) -> Value {
    json!({
        "appointment_id": appointment_id,
        "patient_id": PATIENT,
        "practitioner_id": practitioner_id,
        "scheduled_date": date,
        "slot": { "start": start, "end": end },
        "buffer_duration": null,
        "status": status,
        "reason": null,
        "notes": null,
    })
}

fn valid_booking() -> Value {
    booking(
        "11111111-1111-1111-1111-111111111111",
        PRACTITIONER_A,
        "2026-09-01",
        "09:00:00",
        "09:30:00",
        "requested",
    )
}

#[tokio::test]
async fn appointment_booking_roundtrip() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, body) = post_json(&mut router, "/api/appointments", valid_booking()).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");
    assert_eq!(body["appointment_id"], "11111111-1111-1111-1111-111111111111");
    assert_eq!(body["patient_id"], PATIENT);
    assert_eq!(body["practitioner_id"], PRACTITIONER_A);
    assert_eq!(body["scheduled_date"], "2026-09-01");
    assert_eq!(body["slot"], json!({ "start": "09:00:00", "end": "09:30:00" }));
    assert_eq!(body["status"], "requested");
    assert!(body["created_at"].is_string(), "{body}");
    assert!(body["updated_at"].is_null(), "{body}");

    let (status, schedule) = call(
        &mut router,
        Request::builder().uri("/api/schedule?date=2026-09-01").body(Body::empty()).unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{schedule}");
    assert_eq!(schedule.as_array().unwrap().len(), 1, "{schedule}");
    assert_eq!(schedule[0], body);

    let (status, appointments) = call(
        &mut router,
        Request::builder()
            .uri(format!("/api/patients/{PATIENT}/appointments"))
            .body(Body::empty())
            .unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{appointments}");
    assert_eq!(appointments.as_array().unwrap().len(), 1, "{appointments}");
    assert_eq!(appointments[0], body);
}

#[tokio::test]
async fn appointment_duplicate_returns_conflict() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, _) = post_json(&mut router, "/api/appointments", valid_booking()).await;
    assert_eq!(status, StatusCode::CREATED);

    let (status, body) = post_json(&mut router, "/api/appointments", valid_booking()).await;
    assert_eq!(status, StatusCode::CONFLICT, "{body}");
}

#[tokio::test]
async fn appointment_overlapping_slots_are_rejected() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, _) = post_json(&mut router, "/api/appointments", valid_booking()).await;
    assert_eq!(status, StatusCode::CREATED);

    // overlapping (09:15-09:45 against 09:00-09:30) -> 409
    let overlap = booking(
        "22222222-2222-2222-2222-222222222222",
        PRACTITIONER_A,
        "2026-09-01",
        "09:15:00",
        "09:45:00",
        "requested",
    );
    let (status, body) = post_json(&mut router, "/api/appointments", overlap).await;
    assert_eq!(status, StatusCode::CONFLICT, "{body}");

    // adjacent non-overlapping (09:30-10:00) -> 201
    let adjacent = booking(
        "33333333-3333-3333-3333-333333333333",
        PRACTITIONER_A,
        "2026-09-01",
        "09:30:00",
        "10:00:00",
        "requested",
    );
    let (status, body) = post_json(&mut router, "/api/appointments", adjacent).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");

    // different practitioner, same slot -> 201
    let other_practitioner = booking(
        "44444444-4444-4444-4444-444444444444",
        PRACTITIONER_B,
        "2026-09-01",
        "09:00:00",
        "09:30:00",
        "requested",
    );
    let (status, body) = post_json(&mut router, "/api/appointments", other_practitioner).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");
}

#[tokio::test]
async fn appointment_reschedule_updates_date_slot_and_updated_at() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, _) = post_json(&mut router, "/api/appointments", valid_booking()).await;
    assert_eq!(status, StatusCode::CREATED);

    let request = Request::builder()
        .method("PATCH")
        .uri("/api/appointments/11111111-1111-1111-1111-111111111111")
        .header("content-type", "application/json")
        .body(Body::from(
            json!({
                "scheduled_date": "2026-09-02",
                "slot": { "start": "14:00:00", "end": "14:30:00" },
                "notes": "moved by the front desk"
            })
            .to_string(),
        ))
        .unwrap();
    let (status, body) = call(&mut router, request).await;
    assert_eq!(status, StatusCode::OK, "{body}");
    assert_eq!(body["scheduled_date"], "2026-09-02");
    assert_eq!(body["slot"], json!({ "start": "14:00:00", "end": "14:30:00" }));
    assert_eq!(body["notes"], "moved by the front desk");
    assert_eq!(body["status"], "requested");
    assert!(body["updated_at"].is_string(), "{body}");

    let (status, old_day) = call(
        &mut router,
        Request::builder().uri("/api/schedule?date=2026-09-01").body(Body::empty()).unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{old_day}");
    assert_eq!(old_day.as_array().unwrap().len(), 0, "{old_day}");

    let (status, new_day) = call(
        &mut router,
        Request::builder().uri("/api/schedule?date=2026-09-02").body(Body::empty()).unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{new_day}");
    assert_eq!(new_day.as_array().unwrap().len(), 1, "{new_day}");
}

#[tokio::test]
async fn appointment_reschedule_conflict_and_cancelled_are_rejected() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    post_json(&mut router, "/api/appointments", valid_booking()).await;
    let other = booking(
        "22222222-2222-2222-2222-222222222222",
        PRACTITIONER_A,
        "2026-09-01",
        "10:00:00",
        "10:30:00",
        "requested",
    );
    let (status, _) = post_json(&mut router, "/api/appointments", other).await;
    assert_eq!(status, StatusCode::CREATED);

    // reschedule the 09:00 appointment into the 10:00-10:30 slot -> 409
    let request = Request::builder()
        .method("PATCH")
        .uri("/api/appointments/11111111-1111-1111-1111-111111111111")
        .header("content-type", "application/json")
        .body(Body::from(
            json!({ "slot": { "start": "10:15:00", "end": "10:45:00" } }).to_string(),
        ))
        .unwrap();
    let (status, body) = call(&mut router, request).await;
    assert_eq!(status, StatusCode::CONFLICT, "{body}");

    // cancel then attempt a reschedule -> 409
    let request = Request::builder()
        .method("POST")
        .uri("/api/appointments/22222222-2222-2222-2222-222222222222/cancel")
        .header("content-type", "application/json")
        .body(Body::from("{}"))
        .unwrap();
    let (status, body) = call(&mut router, request).await;
    assert_eq!(status, StatusCode::OK, "{body}");
    assert_eq!(body["status"], "cancelled");

    let request = Request::builder()
        .method("PATCH")
        .uri("/api/appointments/22222222-2222-2222-2222-222222222222")
        .header("content-type", "application/json")
        .body(Body::from(json!({ "scheduled_date": "2026-10-01" }).to_string()))
        .unwrap();
    let (status, body) = call(&mut router, request).await;
    assert_eq!(status, StatusCode::CONFLICT, "{body}");
}

#[tokio::test]
async fn appointment_cancel_sets_status_and_reason() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    post_json(&mut router, "/api/appointments", valid_booking()).await;

    let request = Request::builder()
        .method("POST")
        .uri("/api/appointments/11111111-1111-1111-1111-111111111111/cancel")
        .header("content-type", "application/json")
        .body(Body::from(json!({ "reason": "patient moved away" }).to_string()))
        .unwrap();
    let (status, body) = call(&mut router, request).await;
    assert_eq!(status, StatusCode::OK, "{body}");
    assert_eq!(body["status"], "cancelled");
    assert_eq!(body["reason"], "patient moved away");
    assert!(body["updated_at"].is_string(), "{body}");

    // second cancel -> 409
    let request = Request::builder()
        .method("POST")
        .uri("/api/appointments/11111111-1111-1111-1111-111111111111/cancel")
        .header("content-type", "application/json")
        .body(Body::from("{}"))
        .unwrap();
    let (status, body) = call(&mut router, request).await;
    assert_eq!(status, StatusCode::CONFLICT, "{body}");

    // cancelled appointment no longer blocks a new booking in that slot
    let replacement = booking(
        "22222222-2222-2222-2222-222222222222",
        PRACTITIONER_A,
        "2026-09-01",
        "09:00:00",
        "09:30:00",
        "requested",
    );
    let (status, body) = post_json(&mut router, "/api/appointments", replacement).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");
}

#[tokio::test]
async fn appointment_schedule_supports_practitioner_filter_and_sorting() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    post_json(
        &mut router,
        "/api/appointments",
        booking(
            "11111111-1111-1111-1111-111111111111",
            PRACTITIONER_A,
            "2026-09-01",
            "14:00:00",
            "14:30:00",
            "requested",
        ),
    )
    .await;
    post_json(
        &mut router,
        "/api/appointments",
        booking(
            "22222222-2222-2222-2222-222222222222",
            PRACTITIONER_A,
            "2026-09-01",
            "09:00:00",
            "09:30:00",
            "confirmed",
        ),
    )
    .await;
    post_json(
        &mut router,
        "/api/appointments",
        booking(
            "33333333-3333-3333-3333-333333333333",
            PRACTITIONER_B,
            "2026-09-01",
            "09:00:00",
            "09:30:00",
            "requested",
        ),
    )
    .await;

    let (status, all) = call(
        &mut router,
        Request::builder().uri("/api/schedule?date=2026-09-01").body(Body::empty()).unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{all}");
    let items = all.as_array().unwrap();
    assert_eq!(items.len(), 3, "{all}");
    assert_eq!(items[0]["slot"]["start"], "09:00:00", "{all}");
    assert_eq!(items[1]["slot"]["start"], "09:00:00", "{all}");
    assert_eq!(items[2]["slot"]["start"], "14:00:00", "{all}");

    let uri = format!("/api/schedule?date=2026-09-01&practitioner={PRACTITIONER_A}");
    let (status, filtered) = call(
        &mut router,
        Request::builder().uri(&uri).body(Body::empty()).unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{filtered}");
    let items = filtered.as_array().unwrap();
    assert_eq!(items.len(), 2, "{filtered}");
    for item in items {
        assert_eq!(item["practitioner_id"], PRACTITIONER_A, "{filtered}");
    }
}

#[tokio::test]
async fn appointment_invalid_inputs_are_rejected() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    // malformed JSON
    let (status, body) = call(
        &mut router,
        Request::builder()
            .method("POST")
            .uri("/api/appointments")
            .header("content-type", "application/json")
            .body(Body::from("{not json"))
            .unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    // missing required fields
    let (status, body) = post_json(
        &mut router,
        "/api/appointments",
        json!({ "appointment_id": "11111111-1111-1111-1111-111111111111" }),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    // non-uuid appointment id
    let mut bad = valid_booking();
    bad["appointment_id"] = json!("not-a-uuid");
    let (status, body) = post_json(&mut router, "/api/appointments", bad).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    // non-uuid patient id
    let mut bad = valid_booking();
    bad["patient_id"] = json!("not-a-uuid");
    let (status, body) = post_json(&mut router, "/api/appointments", bad).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    // bad date format
    let mut bad = valid_booking();
    bad["scheduled_date"] = json!("09/01/2026");
    let (status, body) = post_json(&mut router, "/api/appointments", bad).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    // bad slot time
    let mut bad = valid_booking();
    bad["slot"] = json!({ "start": "25:00:00", "end": "09:30:00" });
    let (status, body) = post_json(&mut router, "/api/appointments", bad).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    // end not after start
    let mut bad = valid_booking();
    bad["slot"] = json!({ "start": "09:30:00", "end": "09:00:00" });
    let (status, body) = post_json(&mut router, "/api/appointments", bad).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    // unknown status enum value
    let mut bad = valid_booking();
    bad["status"] = json!("tentative");
    let (status, body) = post_json(&mut router, "/api/appointments", bad).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    // schedule requires a date and rejects invalid dates
    let (status, body) = call(
        &mut router,
        Request::builder().uri("/api/schedule").body(Body::empty()).unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    let (status, body) = call(
        &mut router,
        Request::builder().uri("/api/schedule?date=not-a-date").body(Body::empty()).unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");
}

#[tokio::test]
async fn appointment_unknown_entities_return_404() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let request = Request::builder()
        .method("PATCH")
        .uri("/api/appointments/00000000-0000-0000-0000-000000000000")
        .header("content-type", "application/json")
        .body(Body::from(json!({ "scheduled_date": "2026-10-01" }).to_string()))
        .unwrap();
    let (status, body) = call(&mut router, request).await;
    assert_eq!(status, StatusCode::NOT_FOUND, "{body}");

    let request = Request::builder()
        .method("POST")
        .uri("/api/appointments/00000000-0000-0000-0000-000000000000/cancel")
        .header("content-type", "application/json")
        .body(Body::from("{}"))
        .unwrap();
    let (status, body) = call(&mut router, request).await;
    assert_eq!(status, StatusCode::NOT_FOUND, "{body}");
}

#[tokio::test]
async fn appointment_reply_json_shape_matches_generated_types() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, body) = post_json(&mut router, "/api/appointments", valid_booking()).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");

    let reply = serde_json::from_value::<SchedulingAppointmentReplyV1>(body.clone())
        .expect("created reply must deserialize into the generated SchedulingAppointmentReplyV1");
    let reply_fields = serde_json::to_value(&reply).unwrap();
    let reply_fields = reply_fields.as_object().unwrap();
    for field in [
        "appointment_id",
        "patient_id",
        "practitioner_id",
        "scheduled_date",
        "slot",
        "status",
        "created_at",
    ] {
        assert!(reply_fields.contains_key(field), "missing reply field {field}");
    }

    let request = serde_json::from_value::<SchedulingAppointmentRequestV1>(valid_booking())
        .expect("valid booking must deserialize into the generated SchedulingAppointmentRequestV1");
    assert_eq!(
        serde_json::to_value(&request).unwrap()["slot"],
        json!({ "start": "09:00:00", "end": "09:30:00" })
    );

    // a full reply with buffer_duration present round-trips the generated type
    let mut with_buffer = booking(
        "55555555-5555-5555-5555-555555555555",
        PRACTITIONER_A,
        "2026-09-01",
        "11:00:00",
        "11:30:00",
        "confirmed",
    );
    with_buffer["buffer_duration"] = json!("00:15:00");
    let (status, body) = post_json(&mut router, "/api/appointments", with_buffer).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");
    assert_eq!(body["buffer_duration"], "00:15:00", "{body}");
    assert_eq!(body["status"], "confirmed", "{body}");
}