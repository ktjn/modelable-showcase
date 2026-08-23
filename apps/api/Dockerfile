# Modelable Showcase API image (IMPLEMENTATION_PLAN.md Task 11.1).
#
# Build context MUST be the repository root: `docker build -f apps/api/Dockerfile .`
# (docker-compose.yml sets this). Three stages:
#
#   1. generator - installs the pinned Modelable CLI (.modelable-version) and
#      compiles model/ into generated/rust, deterministically and from
#      scratch every build. This is IMPLEMENTATION_PLAN.md Task 11.1's
#      "dedicated generator stage" design (option 2): `docker compose up
#      --build` from a clean checkout needs no manual `make generate` step.
#      The tradeoff option 2 warns about - slower rebuilds, since Modelable
#      recompiles on every image build - is accepted here in exchange for
#      that guarantee; apps/web/Dockerfile repeats the same stage for its own
#      `--target typescript` output, so the two images stay independently
#      buildable (a `docker build` of just one Dockerfile still works).
#   2. builder - compiles the apps/api Rust binary against showcase-core and
#      the generated crates it consumes, all referenced by relative paths.
#   3. runtime - the compiled binary alone, on a minimal base.
#
# Generated output is never committed or copied from the host; every build
# regenerates it inside the image (UPSTREAM_POLICY.md Sec 7's "no local patch
# layer" extends to not smuggling host-generated artifacts into the image).

FROM ghcr.io/astral-sh/uv:bookworm-slim AS generator
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY .modelable-version ./
COPY model ./model
COPY scripts/install-modelable.sh scripts/modelable-env.sh ./scripts/
RUN bash scripts/install-modelable.sh
RUN bash -lc '. scripts/modelable-env.sh && modelable compile model --target rust --out generated/rust'
RUN bash -lc '. scripts/modelable-env.sh && modelable compile model --target openapi --out generated/openapi'

FROM rust:1-slim-bookworm AS builder
WORKDIR /workspace
COPY --from=generator /workspace/generated/rust ./generated/rust
COPY crates/showcase-core ./crates/showcase-core
COPY apps/api ./apps/api
WORKDIR /workspace/apps/api
RUN cargo build --release

FROM debian:bookworm-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /workspace/apps/api/target/release/modelable-showcase-api /usr/local/bin/modelable-showcase-api
# GET /openapi.json / GET /docs (apps/api/src/docs.rs) need the generated
# document at runtime; this image has no repo checkout to read it from
# on-demand like the dev-server default path does, so it's copied in at
# build time from the generator stage and pointed to explicitly.
COPY --from=generator /workspace/generated/openapi/openapi.json /app/generated/openapi/openapi.json
ENV SHOWCASE_API_ADDR=0.0.0.0:8080
ENV SHOWCASE_OPENAPI_PATH=/app/generated/openapi/openapi.json
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/modelable-showcase-api"]
