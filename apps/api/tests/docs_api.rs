//! Task 9.6 integration test: the developer-facing docs route
//! (UPSTREAM_POLICY.md Sec 5.4). No PostgreSQL/ClickHouse dependency, so it
//! does not skip - `AppState::default()`'s lazy pool/client are never used by
//! these handlers.

use axum::body::Body;
use axum::http::{Request, StatusCode};
use axum::Router;
use http_body_util::BodyExt;
use modelable_showcase_api::{app, AppState};
use tower::ServiceExt;

async fn get(router: Router, uri: &str) -> (StatusCode, String) {
    let response = router.oneshot(Request::builder().uri(uri).body(Body::empty()).unwrap()).await.unwrap();
    let status = response.status();
    let bytes = response.into_body().collect().await.unwrap().to_bytes();
    (status, String::from_utf8_lossy(&bytes).into_owned())
}

#[tokio::test]
async fn docs_page_serves_html_referencing_openapi_json() {
    let (status, body) = get(app(AppState::default()), "/docs").await;
    assert_eq!(status, StatusCode::OK);
    assert!(body.contains("/openapi.json"), "{body}");
    assert!(body.contains("SwaggerUIBundle"), "{body}");
}

#[tokio::test]
async fn openapi_json_serves_the_generated_document_when_present() {
    let openapi_path = format!("{}/../../generated/openapi/openapi.json", env!("CARGO_MANIFEST_DIR"));
    if !std::path::Path::new(&openapi_path).exists() {
        eprintln!("SKIP: {openapi_path} missing; run 'make generate' first");
        return;
    }
    let (status, body) = get(app(AppState::default()), "/openapi.json").await;
    assert_eq!(status, StatusCode::OK);
    let doc: serde_json::Value = serde_json::from_str(&body).expect("response is not valid JSON");
    assert_eq!(doc["openapi"], "3.1.0");
}
