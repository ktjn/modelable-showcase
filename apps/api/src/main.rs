//! Modelable Showcase HTTP API entrypoint (IMPLEMENTATION_PLAN.md Task 9.1).

use modelable_showcase_api::app;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    let addr = std::env::var("SHOWCASE_API_ADDR").unwrap_or_else(|_| "127.0.0.1:8080".into());
    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .unwrap_or_else(|err| panic!("failed to bind {addr}: {err}"));
    tracing::info!("Modelable Showcase API listening on {addr}");

    axum::serve(listener, app(modelable_showcase_api::AppState::default()))
        .await
        .expect("axum server terminated unexpectedly");
}