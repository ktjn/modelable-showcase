//! Developer-facing API docs route (IMPLEMENTATION_PLAN.md Task 9.6,
//! UPSTREAM_POLICY.md Sec 5.4: "expose the generated contract to developers,
//! e.g. through a static API-docs route or local Swagger UI/Scalar viewer").
//!
//! `GET /openapi.json` serves `generated/openapi/openapi.json` verbatim - it
//! is disposable `make generate` output (gitignored), so this reads it from
//! disk at request time rather than embedding it at compile time. `GET
//! /docs` is a small handwritten HTML page loading Swagger UI against that
//! route; per UPSTREAM_POLICY.md Sec 5, "a documentation viewer MAY be
//! handwritten configuration" - only the OpenAPI document itself must not be.
//!
//! The path defaults to the dev-repo-relative location (`CARGO_MANIFEST_DIR`
//! is `apps/api` at compile time), but is overridable via
//! `SHOWCASE_OPENAPI_PATH` (IMPLEMENTATION_PLAN.md Task 11.1:
//! `apps/api/Dockerfile`'s runtime stage has no repo checkout at all, only
//! the compiled binary, so it sets this env var to wherever it copied its own
//! `generated/openapi/openapi.json` from the generator stage).

use axum::http::{header, StatusCode};
use axum::response::{Html, IntoResponse};
use axum::routing::get;
use axum::{Json, Router};
use serde_json::json;

use crate::AppState;

pub fn docs_routes() -> Router<AppState> {
    Router::new().route("/openapi.json", get(openapi_json)).route("/docs", get(docs_page))
}

fn openapi_json_path() -> String {
    std::env::var("SHOWCASE_OPENAPI_PATH")
        .unwrap_or_else(|_| format!("{}/../../generated/openapi/openapi.json", env!("CARGO_MANIFEST_DIR")))
}

async fn openapi_json() -> impl IntoResponse {
    match tokio::fs::read(openapi_json_path()).await {
        Ok(bytes) => (StatusCode::OK, [(header::CONTENT_TYPE, "application/json")], bytes).into_response(),
        Err(_) => (
            StatusCode::NOT_FOUND,
            Json(json!({ "error": "generated/openapi/openapi.json missing - run 'make generate' first" })),
        )
            .into_response(),
    }
}

const DOCS_HTML: &str = r##"<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Modelable Showcase API</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.onload = () => {
        window.ui = SwaggerUIBundle({
          url: "/openapi.json",
          dom_id: "#swagger-ui",
        });
      };
    </script>
  </body>
</html>
"##;

async fn docs_page() -> impl IntoResponse {
    Html(DOCS_HTML)
}
