.DEFAULT_GOAL := help
.PHONY: help bootstrap generate validate probes compat integration e2e determinism acceptance clean up down modelable-version

GENERATED_DIRS := generated dist .modelable
CLEAN_DIRS := $(GENERATED_DIRS) apps/web/node_modules apps/web/dist .pytest_cache

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
	@echo "  e2e              Compose + Playwright"
	@echo "  determinism      double-generation hash comparison"
	@echo "  acceptance       all required non-optional gates"
	@echo "  clean            remove disposable build/test output"
	@echo "  up               docker compose up --build"
	@echo "  down             docker compose down"
	@echo "  modelable-version  print showcase pin + installed Modelable version"

bootstrap:
	./scripts/install-modelable.sh

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
	$(call not_implemented,validate,"Task 17.1 - Finalize command facade")

probes:
	$(call not_implemented,probes,"Task 7.6 - Unified probe target")

compat:
	@. ./scripts/modelable-env.sh; uv run pytest -q tests/conformance/test_model_compatibility.py $(wildcard tests/conformance/test_target_compatibility.py)

integration:
	$(call not_implemented,integration,"Task 17.1 - Finalize command facade")

e2e:
	$(call not_implemented,e2e,"Task 12.1 - Playwright harness")

determinism:
	@. ./scripts/modelable-env.sh; uv run scripts/check-determinism.py

acceptance:
	$(call not_implemented,acceptance,"Task 17.1 - Finalize command facade")

up:
	$(call not_implemented,up,"Phase 11 - Docker product assembly")

down:
	$(call not_implemented,down,"Phase 11 - Docker product assembly")

clean:
	rm -rf $(CLEAN_DIRS)
