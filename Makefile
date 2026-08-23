# Recipes here use bash-only constructs (scripts/modelable-env.sh's
# ${var:=default}/case pattern matching, `( subshell; ) ; status=$?`), and
# Make's default SHELL is /bin/sh - dash on Debian/Ubuntu, which chokes on
# some of that ("Bad substitution"). Force bash explicitly rather than
# rewriting every recipe to be POSIX-sh-safe.
SHELL := /bin/bash

.DEFAULT_GOAL := help
.PHONY: help bootstrap generate validate probes compat integration integration-apicurio integration-marquez e2e determinism acceptance coverage-report wasm-check-generated wasm-test wasm-build wasm-e2e pages-build clean up down modelable-version

GENERATED_DIRS := generated dist .modelable
CLEAN_DIRS := $(GENERATED_DIRS) apps/web/node_modules apps/web/dist apps/web/public/wasm .pytest_cache

# Prints a deterministic, non-zero-exit "not implemented yet" message for a
# target whose real implementation lands in a later IMPLEMENTATION_PLAN.md
# task. Never let a target silently succeed when its implementation is
# missing (IMPLEMENTATION_PLAN.md Task 1.1).
define not_implemented
	@echo "make $(1): not implemented yet." >&2
	@echo "  See IMPLEMENTATION_PLAN.md $(2)." >&2
	@exit 1
endef

help:
	@echo "Modelable Showcase - available targets:"
	@echo "  bootstrap        install project tools/deps"
	@echo "  generate         generate all current implemented targets"
	@echo "  validate         strict model + conformance capability checks"
	@echo "  probes           downstream language/descriptor compilation"
	@echo "  compat           semantic + protobuf + grpc compatibility"
	@echo "  integration      generated artifact + DB + API integration tests"
	@echo "  integration-apicurio  optional Apicurio publish/pull profile (Task 15.2)"
	@echo "  integration-marquez   optional Marquez/OpenLineage sync profile (Task 15.3)"
	@echo "  e2e              Compose + Playwright"
	@echo "  determinism      double-generation hash comparison"
	@echo "  acceptance       all required non-optional gates"
	@echo "  coverage-report  print upstream capability coverage table"
	@echo "  wasm-check-generated  compile clinic-generated Rust for wasm32"
	@echo "  wasm-test        test the portable core and WASM transport"
	@echo "  wasm-build       build the self-contained static browser clinic"
	@echo "  wasm-e2e         run browser-only WASM and Pages journeys"
	@echo "  pages-build      build and validate the GitHub Pages artifact"
	@echo "  clean            remove disposable build/test output"
	@echo "  up               docker compose up --build"
	@echo "  down             docker compose down"
	@echo "  modelable-version  print showcase pin + installed Modelable version"

bootstrap:
	./scripts/install-modelable.sh
	./scripts/install-protoc.sh
	uv run scripts/install-wasm-bindgen.py

modelable-version:
	@echo "showcase pin (.modelable-version): $$(cat .modelable-version)"
	@. ./scripts/modelable-env.sh; \
	if command -v modelable >/dev/null 2>&1; then \
		echo "installed modelable: $$(modelable --version)"; \
	else \
		echo "installed modelable: not installed - run 'make bootstrap' first" >&2; \
	fi
	@if [ -n "$$MODELABLE_REF" ]; then echo "MODELABLE_REF: $$MODELABLE_REF"; fi

generate:
	@. ./scripts/modelable-env.sh; uv run scripts/generate-all.py

validate:
	@. ./scripts/modelable-env.sh; modelable validate ./model --strict
	@. ./scripts/modelable-env.sh; uv run pytest -q \
		tests/conformance/test_valid_fixtures.py \
		tests/conformance/test_invalid_fixtures.py \
		tests/conformance/test_deferred_capabilities.py
	@. ./scripts/modelable-env.sh; uv run scripts/check-capability-coverage.py --strict

probes: generate
	@. ./scripts/modelable-env.sh; \
	uv run pytest -q \
		tests/integration/test_rust_codegen.py \
		tests/integration/test_csharp_codegen.py \
		tests/integration/test_java_codegen.py \
		tests/integration/test_python_codegen.py \
		tests/integration/test_go_codegen.py \
		tests/integration/test_protobuf_codegen.py \
		tests/integration/test_avro_codegen.py
	@cd apps/web && npm install && npm test -- --run && npm run build
	@dotnet test probes/csharp
	@cd probes/java && mvn -q test
	@cd probes/python && uv run pytest -q
	@cd probes/go && go test ./...
	@cargo test --manifest-path apps/api/Cargo.toml

compat:
	@. ./scripts/modelable-env.sh; uv run pytest -q tests/conformance/test_model_compatibility.py $(wildcard tests/conformance/test_target_compatibility.py)

integration:
	@. ./scripts/modelable-env.sh; uv run pytest -q \
		tests/integration/test_model_cli.py \
		tests/integration/test_cli_surface.py \
		tests/integration/test_generate_all.py \
		tests/integration/test_generated_artifacts.py \
		tests/integration/test_postgres_generated_schema.py \
		tests/integration/test_clickhouse_generated_schema.py \
		tests/integration/test_openapi_checkpoint.py \
		tests/integration/test_openapi_contract.py \
		tests/conformance/test_registry_ids.py

integration-apicurio:
	docker compose --profile apicurio up -d apicurio
	@. ./scripts/modelable-env.sh; uv run pytest -q tests/integration/test_apicurio_publish_pull.py
	docker compose stop apicurio

integration-marquez:
	docker compose --profile marquez up -d marquez
	@. ./scripts/modelable-env.sh; uv run pytest -q tests/integration/test_marquez_lineage_sync.py
	docker compose stop marquez marquez-db

e2e: generate
	docker compose down -v
	docker compose up --build -d
	@. ./scripts/modelable-env.sh; uv run scripts/setup-full-database.py
	@cd tests/e2e && npm install && npx playwright install --with-deps chromium
	@( cd tests/e2e && npx playwright test --project=chromium ); status=$$?; \
	docker compose down; \
	exit $$status

determinism:
	@. ./scripts/modelable-env.sh; uv run scripts/check-determinism.py

acceptance:
	$(MAKE) validate
	$(MAKE) compat
	$(MAKE) generate
	$(MAKE) determinism
	docker compose up -d postgres clickhouse
	$(MAKE) probes
	$(MAKE) integration
	$(MAKE) e2e
	@. ./scripts/modelable-env.sh; uv run pytest -q tests/integration/test_lsp_smoke.py

coverage-report:
	@. ./scripts/modelable-env.sh; uv run scripts/coverage-report.py

wasm-check-generated:
	rustup target add wasm32-unknown-unknown
	@. ./scripts/modelable-env.sh; uv run scripts/check-generated-rust-wasm.py

wasm-test: generate
	rustup target add wasm32-unknown-unknown
	cargo test --locked --manifest-path crates/showcase-core/Cargo.toml
	cargo check --locked --target wasm32-unknown-unknown --manifest-path crates/showcase-core/Cargo.toml
	cargo test --locked --manifest-path crates/showcase-wasm/Cargo.toml
	cargo build --locked --release --target wasm32-unknown-unknown --manifest-path crates/showcase-wasm/Cargo.toml

wasm-build:
	uv run scripts/build-showcase-wasm.py
	@cd apps/web && npm ci
	@cd apps/web && VITE_SHOWCASE_RUNTIME=wasm VITE_SHOWCASE_STATIC=true npm run build
	uv run scripts/validate-wasm-pages.py

pages-build: wasm-build

wasm-e2e: generate
	$(MAKE) pages-build
	@cd tests/e2e && npm ci && npx playwright install --with-deps chromium
	@cd tests/e2e && npx playwright test --project=wasm-chromium --project=pages-chromium

up:
	docker compose up --build -d

down:
	docker compose down

clean:
	rm -rf $(CLEAN_DIRS)
