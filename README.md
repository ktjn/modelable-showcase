# Modelable Showcase

Downstream product and acceptance suite for [Modelable](https://github.com/ktjn/modelable), a domain-model compiler that generates typed contracts, database schemas, and API surfaces from `.mdl` source.

## 1. What this repo is

`modelable-showcase` is **Modelable Clinic**, a small fictional outpatient-clinic product, built entirely from generated Modelable artifacts, plus the test/acceptance harness that proves those artifacts actually work end to end - not just that they parse.

It is simultaneously:

- a real product a human can build, start, and click through (patient registration, scheduling, clinical encounters, billing, analytics);
- a consumer of every implemented Modelable target (Rust, TypeScript, C#, Java, Python, Go, SQL for PostgreSQL/ClickHouse, OpenAPI, protobuf/gRPC, FHIR, dbt, OpenMetadata, OpenLineage, ODCS, Avro-adjacent JSON Schema, Markdown docs, event-sink);
- a compiler/language conformance suite (positive/negative/deferred fixtures, compatibility evolution checks, LSP smoke tests);
- a canary that can be pointed at an arbitrary upstream Modelable branch or commit instead of the pinned release.

See [`SPEC.md`](SPEC.md) for the authoritative requirements and Definition of Done, [`UPSTREAM_POLICY.md`](UPSTREAM_POLICY.md) for how upstream gaps are handled (fix Modelable first, never a permanent local workaround), [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) for how it was built task by task, and [`UPSTREAM_FINDINGS.md`](UPSTREAM_FINDINGS.md) for the running log of real Modelable bugs/gaps this showcase has found - check it before re-discovering the same crash twice.

All patient/clinical/billing data anywhere in this repository is synthetic and obviously fictional. **This is a technical showcase, not clinical software.**

## 2. What it tests

| Layer | How |
|---|---|
| Model source (`model/*.mdl`) | `modelable validate --strict`; positive/negative/deferred fixture suites (`tests/conformance/`) |
| Every generated target | `scripts/generate-all.py` compiles all 20 currently-implemented targets; `scripts/check-determinism.py` proves two independent compiles are byte-identical |
| Downstream language compilation | Rust/C#/Java/Python/Go probes actually import, instantiate, and (where the language supports it) resolve generated types - not text greps (`tests/integration/test_*_codegen.py`, `probes/*`) |
| Database DDL | Generated `sql-postgres`/`sql-clickhouse` applied to real Postgres 17/ClickHouse 24.8 containers, round-tripping real rows (`tests/integration/test_postgres_generated_schema.py`, `test_clickhouse_generated_schema.py`) |
| The HTTP API | `apps/api` (Rust/Axum) built directly on generated Rust types, with its own integration test suite against real Postgres/ClickHouse (`apps/api/tests/`) |
| The web app | `apps/web` (React/TypeScript) built directly on generated TypeScript types, unit-tested with Vitest and driven end to end with Playwright (`tests/e2e/`) |
| Compatibility evolution | Schema-evolution and protobuf/gRPC wire-compatibility checks across versions (`tests/conformance/test_model_compatibility.py`, `test_target_compatibility.py`) |
| Language server | A real JSON-RPC client drives `modelable lsp` over stdio - diagnostics, completion, hover, definition, references, rename, formatting (`tests/integration/test_lsp_smoke.py`) |
| Optional integrations | Apicurio Registry publish/pull, Marquez/OpenLineage sync, HL7 FHIR Validator - each behind its own opt-in `make` target, never blocking the core gate |
| Upstream regressions | `.github/workflows/canary.yml` runs the entire suite above against an arbitrary Modelable branch/commit on demand |

## 3. Architecture

```text
model/*.mdl  ──modelable compile──▶  generated/<target>/...
                                          │
                    ┌─────────────────────┼──────────────────────┐
                    ▼                     ▼                      ▼
            generated/rust        generated/sql-postgres   generated/typescript
                    │              generated/sql-clickhouse        │
                    ▼                     │                        ▼
            apps/api (Axum)  ◀────────────┘                apps/web (React/Vite)
                    │                                               │
                    ├── PostgreSQL 17 (patient/scheduling/clinical/billing)
                    ├── ClickHouse 24.8 (appointment/invoice/payment events, analytics)
                    │
                    ▼
            HTTP JSON API  ◀──── nginx reverse proxy ──── apps/web (browser)
```

`apps/api` and `apps/web` are the only two hand-written applications in the repo; everything they depend on (types, request/reply shapes, OpenAPI document, DB schema) is generated from `model/*.mdl`. Both Dockerfiles install the pinned Modelable CLI and compile `model/` from scratch in their own generator stage, so `docker compose up --build` from a clean checkout needs no separate `make generate` step.

## 4. Quick start

```bash
git clone <this-repo>
cd modelable-showcase
make bootstrap          # installs the pinned Modelable CLI + protoc (uv tool install, no global mutation)
docker compose up --build -d
uv run scripts/setup-full-database.py   # applies the full generated Postgres + ClickHouse schema
uv run scripts/seed-demo-data.py        # optional: populate a handful of synthetic patients/appointments/invoices
```

Then open `http://localhost:5173/` (the app) or `http://localhost:8080/docs` (Swagger UI over the generated OpenAPI document). Without the seed step the app starts empty - `seed-demo-data.py` calls the real HTTP API (never a direct DB write) to create a few fictional patients (SPEC.md's synthetic-data rule) with appointments, encounters, observations, and invoices/payments, so `/patients`, `/schedule`, and `/analytics` all have something to show.

| Service | Port (bound to `127.0.0.1`) | Notes |
|---|---|---|
| `web` | `5173` | React SPA, served by nginx, proxies `/api`/`/openapi.json`/`/docs` to `api` |
| `api` | `8080` | Axum API directly - `/health`, `/docs`, `/openapi.json` |
| `postgres` | `5433` | `psql -h 127.0.0.1 -p 5433 -U showcase showcase` |
| `clickhouse` | `8123` | HTTP interface |

## 5. Run acceptance

```bash
make acceptance
```

Runs, in fail-fast order: `validate` → `compat` → `generate` → `determinism` → `probes` → `integration` → `e2e` → LSP smoke. This is what `.github/workflows/ci.yml` runs on every push/PR, split into parallel jobs (`model`, `generate`, one job per language, `databases`, `product`, `e2e`).

Optional profiles not part of `acceptance` (each needs its own local service, started on demand):

```bash
make integration-apicurio   # Apicurio Registry publish/pull
make integration-marquez    # Marquez/OpenLineage lineage sync
uv run scripts/validate-fhir-profiles.py   # HL7 FHIR Validator (needs Java + scripts/install-fhir-validator.sh)
```

`make` itself must be on `PATH` (not preinstalled on every OS); every target's underlying command is also runnable directly - see the target's recipe in [`Makefile`](Makefile) if `make` isn't available.

## 6. Run against a Modelable upstream ref

```bash
MODELABLE_REF=main make bootstrap && make acceptance
```

`scripts/install-modelable.sh` switches into canary mode whenever `MODELABLE_REF` is set (a branch, tag, or full commit SHA on `ktjn/modelable`), installing from source instead of the pinned PyPI release, and resolves/logs the exact commit before installing. The same thing is available as a one-click GitHub Actions run: **Actions → Canary → Run workflow**, with `modelable_ref` as input ([`.github/workflows/canary.yml`](.github/workflows/canary.yml)).

## 7. Generated artifact policy

Everything under `generated/`, `dist/`, and `.modelable/` is disposable build output - never edit it by hand, never commit it (all gitignored), and never treat it as source of truth. `model/registry-ids.lock` is the one deliberate exception: it is Modelable's semantic-ID allocation ledger, durable state that must survive across compiles, and is committed.

If a generated artifact is wrong, the fix belongs in `model/*.mdl` (if the showcase is using Modelable incorrectly) or upstream in Modelable itself (if the emitter is wrong) - never a permanent script that rewrites generated output. See [`UPSTREAM_POLICY.md`](UPSTREAM_POLICY.md) §6-7 for the full decision tree, and [`UPSTREAM_FINDINGS.md`](UPSTREAM_FINDINGS.md) for every upstream gap found this way, each with a minimal reproduction and root cause read from Modelable's own source.

## 8. Synthetic-data warning

Every patient name, date of birth, diagnosis, invoice, and payment anywhere in this repository - fixtures, tests, seed scripts, screenshots - is synthetic and fictional. No real patient data may ever be committed here. This is a technical demonstration of a code generator, not a clinical system, and must never be mistaken for one.

## 9. Troubleshooting prerequisites

| Symptom | Cause | Fix |
|---|---|---|
| `make bootstrap` fails installing Modelable | `uv` not installed | Install uv: https://docs.astral.sh/uv/getting-started/installation/ |
| `modelable compile --descriptor-set` or protobuf/gRPC probes fail to find `protoc` | Didn't source the env script | `source scripts/modelable-env.sh` (also run automatically inside every `make` recipe) |
| `apps/api` integration tests fail with `relation "..." does not exist` | Schema not applied to a fresh Postgres | `uv run scripts/setup-full-database.py` |
| `make bootstrap && make generate` on Windows with only Git Bash | `install-protoc.sh` targets POSIX shells | Follow the script's own printed instructions: place `protoc-<version>-win64.zip`'s `bin/` on `PATH` under `tools/protoc-<version>/bin` |
| `test_fhir_profiles_pass_the_hl7_validator` / `validate-fhir-profiles.py` skip | Optional HL7 FHIR Validator not installed | `./scripts/install-fhir-validator.sh` (requires Java; pinned + checksum-verified, not part of `make bootstrap`) |
| `integration-apicurio`/`integration-marquez` tests skip | Their optional Compose profile isn't running | `docker compose --profile apicurio up -d apicurio` / `docker compose --profile marquez up -d marquez` first |
| `docker compose up --build` succeeds but the app 500s on every request | Schema not applied yet (compose does not apply DB schema automatically) | `uv run scripts/setup-full-database.py` after the containers are healthy |
