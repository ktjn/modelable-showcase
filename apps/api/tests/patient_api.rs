//! Task 9.2 integration tests: the generated Patient API against the showcase
//! PostgreSQL. These skip (early-return) when the showcase DB is unreachable;
//! run `docker compose up -d` to execute them for real.

use std::time::Duration;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use axum::Router;
use clinic_core::patient::patient_address_v0::PatientAddressV0;
use clinic_core::patient::patient_contact_details_v0::PatientContactDetailsV0;
use clinic_core::patient::patient_id::PatientId;
use clinic_core::patient::patient_patient_request_v2::PatientPatientRequestV2;
use http_body_util::BodyExt;
use modelable_showcase_api::{app, AppState};
use serde_json::{json, Value};
use tower::ServiceExt;
use uuid::Uuid;

async fn db_ready(state: &AppState) -> bool {
    tokio::time::timeout(
        Duration::from_secs(4),
        sqlx::query_scalar::<_, i32>("SELECT 1").fetch_one(&state.pool),
    )
    .await
    .map(|result| result.is_ok())
    .unwrap_or(false)
}

async fn db_lock() -> tokio::sync::MutexGuard<'static, ()> {
    static LOCK: tokio::sync::Mutex<()> = tokio::sync::Mutex::const_new(());
    LOCK.lock().await
}

async fn app_ready() -> Option<Router> {
    let state = AppState::default();
    if !db_ready(&state).await {
        eprintln!(
            "SKIP: showcase PostgreSQL unreachable; run 'docker compose up -d' \
             to exercise the Patient API integration tests"
        );
        return None;
    }
    sqlx::query("TRUNCATE TABLE patient_db")
        .execute(&state.pool)
        .await
        .expect("failed to TRUNCATE patient_db");
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

async fn post_patient(router: &mut Router, body: Value) -> (StatusCode, Value) {
    let request = Request::builder()
        .method("POST")
        .uri("/api/patients")
        .header("content-type", "application/json")
        .body(Body::from(body.to_string()))
        .unwrap();
    call(router, request).await
}

fn request_body(
    patient_id: &str,
    legal_name: &str,
    email: &str,
    phone: &str,
) -> Value {
    json!({
        "patient_id": patient_id,
        "legal_name": legal_name,
        "preferred_name": null,
        "date_of_birth": "1985-06-15",
        "contact": {
            "email": email,
            "phone": phone,
        },
        "address": {
            "street": "42 Market Street",
            "city": "Brisbane",
            "postal_code": "4000",
            "country": "Australia",
        },
        "preferred_language": "en",
        "alternate_phone_numbers": null,
        "notes": null,
        "clinical_notes": null,
    })
}

fn valid_request() -> Value {
    request_body(
        "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d",
        "Ada Lovelace",
        "ada@example.test",
        "+61 400 000 000",
    )
}

#[tokio::test]
async fn patient_create_fetch_list_roundtrip() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, body) = post_patient(&mut router, valid_request()).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");
    assert_eq!(body["patient_id"], "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d");
    assert_eq!(body["legal_name"], "Ada Lovelace");
    assert_eq!(body["preferred_language"], "en");
    assert!(body["created_at"].is_string(), "{body}");
    assert!(body["updated_at"].is_null(), "{body}");

    let id = body["patient_id"].as_str().unwrap();
    let request = Request::builder()
        .uri(format!("/api/patients/{id}"))
        .body(Body::empty())
        .unwrap();
    let (status, fetched) = call(&mut router, request).await;
    assert_eq!(status, StatusCode::OK, "{fetched}");
    assert_eq!(fetched, body);

    let (status, list) = call(
        &mut router,
        Request::builder().uri("/api/patients").body(Body::empty()).unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{list}");
    let items = list.as_array().unwrap();
    assert_eq!(items.len(), 1);
    assert_eq!(items[0], body);
}

#[tokio::test]
async fn patient_create_generates_server_timestamps() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, body) = post_patient(&mut router, valid_request()).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");
    let created_at = body["created_at"].as_str().unwrap();
    chrono::DateTime::parse_from_rfc3339(created_at)
        .expect("created_at must be a server-generated RFC3339 timestamp");
    assert!(body["updated_at"].is_null(), "{body}");
}

#[tokio::test]
async fn patient_duplicate_returns_conflict() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, _) = post_patient(&mut router, valid_request()).await;
    assert_eq!(status, StatusCode::CREATED);

    let (status, body) = post_patient(&mut router, valid_request()).await;
    assert_eq!(status, StatusCode::CONFLICT, "{body}");
    assert!(body["error"].as_str().unwrap().contains("already exists"), "{body}");
}

#[tokio::test]
async fn patient_invalid_bodies_return_400() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    // malformed JSON
    let (status, body) = call(
        &mut router,
        Request::builder()
            .method("POST")
            .uri("/api/patients")
            .header("content-type", "application/json")
            .body(Body::from("{not json"))
            .unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");
    assert!(body["error"].is_string(), "{body}");

    // valid JSON but missing required fields (legal_name, date_of_birth)
    let (status, body) = call(
        &mut router,
        Request::builder()
            .method("POST")
            .uri("/api/patients")
            .header("content-type", "application/json")
            .body(Body::from(
                json!({ "patient_id": "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d" }).to_string(),
            ))
            .unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    // invalid patient id (not a uuid)
    let mut invalid = valid_request();
    invalid["patient_id"] = json!("not-a-uuid");
    let (status, body) = post_patient(&mut router, invalid).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");

    // invalid date_of_birth format
    let mut invalid = valid_request();
    invalid["date_of_birth"] = json!("06/15/1985");
    let (status, body) = post_patient(&mut router, invalid).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");
}

#[tokio::test]
async fn patient_get_unknown_id_returns_404() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let request = Request::builder()
        .uri("/api/patients/00000000-0000-0000-0000-000000000000")
        .body(Body::empty())
        .unwrap();
    let (status, body) = call(&mut router, request).await;
    assert_eq!(status, StatusCode::NOT_FOUND, "{body}");
}

#[tokio::test]
async fn patient_get_invalid_id_returns_400() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let request = Request::builder()
        .uri("/api/patients/not-a-uuid")
        .body(Body::empty())
        .unwrap();
    let (status, body) = call(&mut router, request).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");
}

#[tokio::test]
async fn patient_search_by_name_and_email() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    post_patient(
        &mut router,
        request_body(
            "11111111-1111-1111-1111-111111111111",
            "Grace Hopper",
            "grace@example.test",
            "+61 411 111 111",
        ),
    )
    .await;
    post_patient(
        &mut router,
        request_body(
            "22222222-2222-2222-2222-222222222222",
            "Alan Turing",
            "alan@example.test",
            "+61 422 222 222",
        ),
    )
    .await;

    let (status, by_name) = call(
        &mut router,
        Request::builder()
            .uri("/api/patients?name=grace")
            .body(Body::empty())
            .unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{by_name}");
    let items = by_name.as_array().unwrap();
    assert_eq!(items.len(), 1, "{by_name}");
    assert_eq!(items[0]["legal_name"], "Grace Hopper");

    let (status, by_email) = call(
        &mut router,
        Request::builder()
            .uri("/api/patients?email=alan")
            .body(Body::empty())
            .unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{by_email}");
    let items = by_email.as_array().unwrap();
    assert_eq!(items.len(), 1, "{by_email}");
    assert_eq!(items[0]["legal_name"], "Alan Turing");

    let (status, by_email) = call(
        &mut router,
        Request::builder()
            .uri("/api/patients?email=nobody@example.test")
            .body(Body::empty())
            .unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{by_email}");
    assert_eq!(by_email.as_array().unwrap().len(), 0);

    let (status, all) = call(
        &mut router,
        Request::builder().uri("/api/patients").body(Body::empty()).unwrap(),
    )
    .await;
    assert_eq!(status, StatusCode::OK, "{all}");
    assert_eq!(all.as_array().unwrap().len(), 2, "{all}");
}

#[tokio::test]
async fn patient_unknown_query_parameters_rejected() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let request = Request::builder()
        .uri("/api/patients?oops=1")
        .body(Body::empty())
        .unwrap();
    let (status, body) = call(&mut router, request).await;
    assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");
}

#[tokio::test]
async fn patient_reply_json_shape_matches_generated_types() {
    let _guard = db_lock().await;
    let Some(mut router) = app_ready().await else { return };

    let (status, body) = post_patient(&mut router, valid_request()).await;
    assert_eq!(status, StatusCode::CREATED, "{body}");

    // every populated field of the generated reply projection is present in
    // the JSON; None optionals are omitted by the generated
    // `skip_serializing_if` attributes.
    let reply_fields = body.as_object().unwrap();
    let populated = [
        "patient_id",
        "legal_name",
        "date_of_birth",
        "contact",
        "address",
        "preferred_language",
        "created_at",
    ];
    for field in populated {
        assert!(reply_fields.contains_key(field), "missing field {field}");
    }
    let omitted = [
        "preferred_name",
        "alternate_phone_numbers",
        "notes",
        "clinical_notes",
        "updated_at",
    ];
    for field in omitted {
        assert!(!reply_fields.contains_key(field), "unexpected field {field}");
    }
    assert_eq!(reply_fields.len(), populated.len());

    // A JSON document that spells out every generated reply field (None values
    // explicit) must deserialize into the generated PatientPatientReplyV2 and
    // serialize back to the identical field set.
    let full = json!({
        "patient_id": "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d",
        "legal_name": "Ada Lovelace",
        "preferred_name": null,
        "date_of_birth": "1985-06-15",
        "contact": { "email": "ada@example.test", "phone": "+61 400 000 000" },
        "address": {
            "street": "42 Market Street",
            "city": "Brisbane",
            "postal_code": "4000",
            "country": "Australia",
        },
        "preferred_language": "en",
        "alternate_phone_numbers": null,
        "notes": null,
        "clinical_notes": null,
        "created_at": "2026-08-16T00:00:00Z",
        "updated_at": null,
    });
    let reply = serde_json::from_value::<clinic_core::patient::patient_patient_reply_v2::PatientPatientReplyV2>(
        full,
    )
    .expect("full reply JSON must deserialize into the generated PatientPatientReplyV2");
    assert_eq!(serde_json::to_value(&reply).unwrap().as_object().unwrap().len(), populated.len());

    let request = serde_json::from_value::<PatientPatientRequestV2>(valid_request())
        .expect("valid request JSON must deserialize into the generated PatientPatientRequestV2");
    assert_eq!(request.patient_id, PatientId(Uuid::parse_str(
        "9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d"
    ).unwrap()));

    // the synthetic request used by the API is exactly the generated shape;
    // None optionals are omitted on serialization (skip_serializing_if)
    let request_fields = serde_json::to_value(&request).unwrap();
    let request_fields = request_fields.as_object().unwrap();
    let expected_request_fields = [
        "patient_id",
        "legal_name",
        "date_of_birth",
        "contact",
        "address",
        "preferred_language",
    ];
    for field in expected_request_fields {
        assert!(request_fields.contains_key(field), "missing request field {field}");
    }
    let omitted_request_fields = [
        "preferred_name",
        "alternate_phone_numbers",
        "notes",
        "clinical_notes",
    ];
    for field in omitted_request_fields {
        assert!(!request_fields.contains_key(field), "unexpected request field {field}");
    }
    assert_eq!(request_fields.len(), expected_request_fields.len());
}

#[test]
fn generated_value_object_shapes_roundtrip_via_json() {
    let contact = PatientContactDetailsV0 {
        email: Some("ada@example.test".into()),
        phone: None,
    };
    let contact_json = serde_json::to_value(&contact).unwrap();
    assert_eq!(contact_json, json!({ "email": "ada@example.test" }));
    let address = PatientAddressV0 {
        street: "42 Market Street".into(),
        city: "Brisbane".into(),
        postal_code: "4000".into(),
        country: "Australia".into(),
    };
    let address_json = serde_json::to_value(&address).unwrap();
    assert_eq!(
        address_json,
        json!({
            "street": "42 Market Street",
            "city": "Brisbane",
            "postal_code": "4000",
            "country": "Australia",
        })
    );
}