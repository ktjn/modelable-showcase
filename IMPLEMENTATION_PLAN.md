# Modelable Showcase Implementation Plan

**Specification:** [`SPEC.md`](SPEC.md)  
**Target audience:** implementation agents with limited repository context  
**Rule:** implement tasks in order unless a task explicitly says it may run in parallel.

## 0. Operating rules for implementation agents

Read `SPEC.md` completely before changing code.

For every task:

1. Inspect the current repository before editing.
2. Inspect the actual installed/upstream Modelable CLI before inventing `.mdl` syntax or command flags.
3. Write or update tests in the same task as implementation.
4. Run the task-specific verification commands.
5. Do not continue to the next task with unexplained failures.
6. Keep generated output out of git unless the task explicitly says otherwise.
7. Prefer the smallest implementation that satisfies the specification.
8. Do not add a second handwritten domain model alongside generated Modelable contracts.
9. Do not implement deferred Modelable runtime features in this repository.
10. When Modelable behavior differs from this plan, verify upstream `main`, then update this plan/spec deliberately rather than adding compatibility hacks silently.

### Required source of truth checks

Before writing the first `.mdl` file, run:

```bash
modelable --version
modelable capabilities
modelable capabilities --format json
modelable compile --help
modelable validate --help
```

If working directly against upstream source instead of a release, install it first, then run the same commands.

Do not copy syntax from old archived Modelable plans without verifying the current parser accepts it.

### Commit strategy

Prefer one commit per numbered task or coherent sub-task. A task is complete only when its acceptance commands pass.

Suggested commit prefixes:

```text
chore: bootstrap showcase toolchains
feat(model): add patient domain
feat(api): add patient endpoints
test(conformance): add invalid CEL fixtures
ci: add downstream language matrix
```

---

# Phase 1 — Repository bootstrap

## Task 1.1 — Add repository entrypoint and developer commands

### Goal

Create the minimal repository skeleton and stable command façade without implementing product behavior yet.

### Create

```text
README.md
.gitignore
.editorconfig
Makefile
scripts/
model/
apps/web/
apps/api/
probes/csharp/
probes/java/
probes/python/
probes/go/
compat/
tests/conformance/valid/
tests/conformance/invalid/
tests/conformance/deferred/
tests/integration/
tests/e2e/
generated/
```

Git does not track empty directories. Add `.gitkeep` only where required temporarily; remove it when real files arrive.

### `.gitignore`

At minimum ignore:

```text
generated/
dist/
.modelable/
node_modules/
target/
.venv/
__pycache__/
.pytest_cache/
playwright-report/
test-results/
.env
.env.*
!.env.example
```

Do **not** ignore `model/registry-ids.lock`.

### `Makefile`

Add placeholders with useful failure messages for:

```text
bootstrap
generate
validate
probes
compat
integration
e2e
determinism
acceptance
clean
up
down
modelable-version
```

Initially, `make acceptance` may call only the checks that exist. Expand it after every phase. Never leave a target silently succeeding when its implementation is missing; either implement it or print a clear `not implemented yet` error until the task that enables it.

### `README.md`

Keep it concise:

- purpose;
- upstream Modelable link;
- `SPEC.md` and `IMPLEMENTATION_PLAN.md` links;
- eventual `docker compose up --build` command;
- eventual `make acceptance` command;
- warning that all data is synthetic.

### Acceptance

```bash
make modelable-version
make clean
```

Both commands must run predictably. `make acceptance` may still fail with an explicit bootstrap message at this stage.

---

## Task 1.2 — Pin and install Modelable

### Goal

Provide one reproducible release mode and one upstream-ref canary mode.

### Create

```text
.modelable-version
scripts/install-modelable.sh
scripts/modelable-env.sh
```

### Requirements

`.modelable-version` contains exactly one released version string, for example:

```text
1.7.0
```

Use the latest verified stable release at implementation time, not necessarily that example.

`scripts/install-modelable.sh` behavior:

1. If `MODELABLE_REF` is unset, install the version from `.modelable-version` using the supported release installation path.
2. If `MODELABLE_REF` is set, install Modelable from `https://github.com/ktjn/modelable` at that ref.
3. Print the resulting `modelable --version`.
4. If installing from git, resolve and print the exact upstream commit SHA when possible.
5. Fail on installation errors.

Avoid global machine mutation when practical. Prefer a project-local tool environment or `uv tool` mechanism that CI can reproduce.

### Update Makefile

`make bootstrap` installs Modelable and later tool dependencies.

`make modelable-version` prints:

- showcase pin;
- installed Modelable version;
- `MODELABLE_REF` if supplied.

### Tests

Add a shell smoke script or CI-ready command proving:

```bash
./scripts/install-modelable.sh
modelable capabilities --format json >/tmp/modelable-capabilities.json
```

### Acceptance

```bash
make bootstrap
make modelable-version
modelable capabilities --format json | python -m json.tool >/dev/null
```

---

## Task 1.3 — Capability coverage manifest infrastructure

### Goal

Make upstream capability drift visible before implementing specific coverage.

### Create

```text
tests/conformance/capability-coverage.yaml
scripts/check-capability-coverage.py
```

### Manifest schema

Use a simple explicit structure, for example:

```yaml
capabilities:
  target:json-schema:
    coverage: probe
    test: tests/integration/test_generated_artifacts.py::test_json_schema
  sql_dialect:postgres:
    coverage: product
    test: model/patient.mdl
  model_kind:entity:
    coverage: product
    test: model/patient.mdl
  annotation:pii:
    coverage: product
    test: model/patient.mdl
  deferred_feature:composite-keys:
    coverage: deferred
    test: tests/conformance/deferred/composite-key.mdl
```

`modelable capabilities --format json` reports exactly five capability categories: `target`, `sql_dialect`, `model_kind`, `annotation`, `deferred_feature`. The checker MUST flatten and require coverage for all five, not just the ones illustrated above — `sql_dialect` is easy to miss since it currently has only two entries (`postgres`, `clickhouse`), both already exercised by the product.

Targets that are only accepted in `.mdl` `generate {}` block vocabulary but have no `compile --target` implementation (for example `openapi`, `avro`, `asyncapi` at the time this plan was last verified against upstream) do **not** appear in `capabilities --format json` at all and therefore need no manifest entry. Do not invent placeholder capability keys for grammar-level vocabulary that the compiler does not yet expose as a real target — confirm absence with `modelable compile --help` before assuming a gap here.

Allowed `coverage` values:

```text
product
probe
fixture
deferred
excluded
```

`excluded` requires a non-empty `reason`.

### Checker behavior

`scripts/check-capability-coverage.py` MUST:

1. run `modelable capabilities --format json`;
2. flatten capability categories into stable keys such as `target:<name>`;
3. load YAML manifest;
4. fail if any upstream capability is missing;
5. fail if local manifest contains an unknown capability unless explicitly marked historical with a documented reason;
6. fail if upstream status is implemented but local coverage is `deferred`;
7. fail if upstream status is deferred but local coverage is `product` unless an explicit override documents why;
8. verify referenced path exists when `test` is a path;
9. print a compact coverage summary grouped by category/status.

Use Python standard library plus PyYAML if needed. Add the dependency explicitly rather than depending on a transitive package.

### Initial manifest

Populate every capability from the current binary. Entries may temporarily point at `TODO` only if the checker explicitly understands a temporary `planned` field and `make acceptance` is not yet enabled. Remove all planned placeholders by the final phase.

Better approach: mark only completed coverage and have this task's checker run in non-strict bootstrap mode. Add `--strict` later in Task 10.1.

### Acceptance

```bash
python scripts/check-capability-coverage.py
```

Output must identify current gaps clearly.

---

# Phase 2 — Canonical Modelable workspace

## Task 2.1 — Create the workspace and patient domain

### Goal

Establish the first real Modelable workspace with versioning, semantic types, governance, indexes, and auto projections.

### Create

```text
model/workspace.mdl
model/patient.mdl
model/registry-ids.lock
```

### Before editing

Inspect current upstream examples for:

- workspace syntax;
- `package {}` syntax;
- semantic type syntax;
- index syntax;
- access syntax;
- auto projection syntax;
- supported classification values.

Use current accepted syntax only.

### `workspace.mdl`

Define workspace name `modelable-clinic`.

Add Rust package grouping only if current upstream parser/implementation accepts it. Initial desired groups:

```text
clinic-core -> patient, scheduling
clinical-core -> clinical, audit
billing-core -> billing, reporting
```

If this creates an actual package dependency cycle, change the grouping and document why in `README.md` or an ADR. Do not work around package-graph validation.

### `patient.mdl`

Create realistic definitions:

- `semantic PatientId: uuid(7)` or the current legal equivalent;
- at least one `registry: true` semantic;
- `value Address`;
- `value ContactDetails`;
- `entity Patient @1`;
- `entity Patient @2 (additive)`;
- compatibility-only breaking `Patient @3` only if keeping all three versions in one canonical file does not make the live product awkward; otherwise keep v3 under `compat/` later;
- index for current patient version;
- auto projections `db`, `request`, `reply`, `event` for live version.

Use meaningful governance:

- patient ID: internal classification;
- legal name: PII;
- email/phone/address: PII;
- optional notes should not contain fake secrets;
- at least one field-level owner override;
- at least one deprecated field in v2;
- server-generated `createdAt`/`updatedAt`.

Include access metadata using currently supported syntax.

### Registry IDs

Run compile once to create/update `model/registry-ids.lock` using the supported CLI flags/path behavior. Commit the file.

### Tests

Create:

```text
tests/integration/test_model_cli.py
```

Use subprocess calls to the actual CLI. Initial tests:

- strict validation succeeds;
- resolve `patient.Patient@1` succeeds;
- resolve live version succeeds;
- lineage on canonical model succeeds;
- auto projection inspection succeeds if current CLI exposes it.

Do not import Modelable Python internals in these downstream tests.

### Acceptance

```bash
modelable validate model --strict
modelable resolve patient.Patient@1 --path model
pytest -q tests/integration/test_model_cli.py
```

Update capability coverage entries for features now exercised.

---

## Task 2.2 — Add scheduling domain

### Create

```text
model/scheduling.mdl
```

### Required definitions

- semantic `AppointmentId`;
- semantic `PractitionerId` if needed;
- value `TimeRange` if current model rules make it useful;
- `Appointment` entity/aggregate;
- appointment status event;
- current-version index declaration;
- auto projections.

### Product fields

At minimum:

```text
appointmentId
patientId/ref
practitionerId
start
end or duration
status
reason?
notes?
createdAt
updatedAt?
```

Prefer a representation that exercises `date`, `time`, `duration`, and `timestamp` naturally without creating contradictory duplicate state. If all cannot be natural in the live model, put extra type coverage in valid fixtures later.

### Indexes

Create indexes for:

- patient + chronological lookup;
- practitioner + chronological lookup;
- status lookup.

Use `sort` and one descending sort somewhere if current syntax supports it.

### Tests

Extend CLI integration tests with:

- resolve appointment;
- verify auto projection names;
- compile `sql-postgres` and assert secondary index statements appear for the relevant projection/table where upstream semantics produce them.

Do not assert entire SQL files byte-for-byte here; determinism is a separate suite.

### Acceptance

```bash
modelable validate model --strict
modelable compile model --target sql-postgres --out generated/sql/postgres
pytest -q tests/integration/test_model_cli.py
```

---

## Task 2.3 — Add clinical domain

### Create

```text
model/clinical.mdl
```

### Required definitions

- `EncounterId` semantic;
- at least one chained semantic type;
- `Encounter`;
- `Observation`;
- `Diagnosis` value;
- one nested object/value used by observations;
- FHIR-oriented projections sourced from models named `Patient`, `Observation`, and `Encounter` as required by the current emitter.

### Type coverage

Use natural fields such as:

- temperature: decimal or float;
- weight: decimal;
- blood pressure systolic/diastolic: fixed-width unsigned ints;
- pulse: fixed-width unsigned int;
- device payload digest: `binary(32)` if legal/current;
- measurement metadata: map/json;
- recorded time: timestamp;
- diagnosis codes: array;
- structured measurement object.

Do not force every Modelable primitive into the product domain. Leave pathological cases for Task 3.1.

### Semantic ambiguity

Define a domain-qualified semantic reference from `clinical` to a semantic type declared elsewhere. The successful case belongs here; ambiguous failure belongs in Task 3.2.

### Tests

- strict validation;
- compile JSON Schema;
- compile FHIR profiles;
- assert at least Patient/Observation/Encounter-derived profiles use intended resource bases rather than all falling back to generic `Basic` if that is current upstream behavior;
- parse generated FHIR JSON.

### Acceptance

```bash
modelable validate model --strict
modelable compile model --target json-schema --out generated/jsonschema
modelable compile model --target fhir-profile --out generated/fhir
pytest -q tests/integration
```

---

## Task 2.4 — Add billing, audit, and reporting domains

### Create

```text
model/billing.mdl
model/audit.mdl
model/reporting.mdl
```

### Billing

Add:

- `InvoiceId` semantic;
- `InvoiceLine` value;
- `Invoice` aggregate/entity;
- `PaymentReceived` event;
- indexes;
- auto projections;
- money as `decimal(p,s)`;
- arrays of lines;
- invoice/payment status enums;
- references to patient/appointment where appropriate.

Do not add compatibility-only reservation complexity to live product yet unless it is naturally valid. Task 4 handles historical fixtures.

### Audit

Add `AuditEntry` event with:

- timestamp;
- actor identifier;
- subject reference/identifier;
- action enum;
- binary digest/signature representation;
- JSON metadata;
- internal/restricted classification as appropriate.

### Reporting

Implement at least:

- `PatientSummary`;
- `DailySchedule`;
- `PatientClinicalSummary`;
- `OutstandingInvoices`;
- `PractitionerRevenue`;
- `MonthlyClinicStats`.

Collectively use current valid syntax for:

- joins;
- left joins;
- where;
- group by;
- direct mappings;
- computed fields;
- `pick`;
- `omit`;
- classification/PII selectors;
- aggregate functions;
- deterministic CEL string/arithmetic/logical/ternary functions.

If a desired function is not in the current capability/language reference, replace it with one that is. Do not add unsupported syntax simply because this plan names the concept.

### Tests

Add explicit lineage assertions using CLI output for representative fields:

- patient name in `PatientSummary` traces to patient model;
- clinical aggregate traces to observation source;
- revenue aggregate traces to invoice/payment source.

Prefer structured output if CLI supports it. Otherwise assert minimal stable substrings.

### Acceptance

```bash
modelable validate model --strict
modelable lineage reporting.PatientSummary@1 --path model
modelable lineage reporting.PractitionerRevenue@1 --path model
pytest -q tests/integration
```

At end of Phase 2, all canonical `.mdl` must validate strictly.

---

# Phase 3 — Edge-case and diagnostic conformance

## Task 3.1 — Positive edge fixtures

### Goal

Cover legal edge cases without damaging product readability.

### Create focused files

Names may be adjusted, but keep one concern per file where practical:

```text
tests/conformance/valid/numeric-widths.mdl
tests/conformance/valid/fixed-binary.mdl
tests/conformance/valid/optional-arrays.mdl
tests/conformance/valid/array-enums.mdl
tests/conformance/valid/maps.mdl
tests/conformance/valid/nested-objects.mdl
tests/conformance/valid/json.mdl
tests/conformance/valid/semantic-chain.mdl
tests/conformance/valid/qualified-semantics.mdl
tests/conformance/valid/cel-precedence.mdl
tests/conformance/valid/cel-ternary.mdl
tests/conformance/valid/default-values.mdl
tests/conformance/valid/version-ranges.mdl
tests/conformance/valid/protobuf-reservations.mdl
tests/conformance/valid/annotation-selectors.mdl
```

### Test runner

Create:

```text
tests/conformance/test_valid_fixtures.py
```

Parameterize over all `.mdl` files in `valid/` and run the actual CLI validator. Every file must succeed.

For emitter-specific edges, add targeted compilation assertions. Examples:

- `u128/i128` output is representable or emits the documented target warning;
- optional arrays compile in Rust;
- arrays of inline enums compile in TypeScript;
- legal maps compile in Protobuf;
- fixed binary metadata appears in JSON Schema.

Do not force every valid fixture through every target if upstream explicitly documents a lossy/unsupported target mapping. Record the coverage classification instead.

### Acceptance

```bash
pytest -q tests/conformance/test_valid_fixtures.py
```

---

## Task 3.2 — Negative fixtures

### Create

```text
tests/conformance/invalid/missing-key.mdl
tests/conformance/invalid/composite-key.mdl
tests/conformance/invalid/key-on-event.mdl
tests/conformance/invalid/unknown-ref.mdl
tests/conformance/invalid/unknown-semantic.mdl
tests/conformance/invalid/semantic-cycle.mdl
tests/conformance/invalid/ambiguous-semantic.mdl
tests/conformance/invalid/index-unknown-field.mdl
tests/conformance/invalid/index-duplicate-name.mdl
tests/conformance/invalid/additive-marked-breaking-change.mdl
tests/conformance/invalid/unresolved-version-range.mdl
tests/conformance/invalid/pick-duplicate-output.mdl
tests/conformance/invalid/invalid-cel-function.mdl
tests/conformance/invalid/cel-type-mismatch.mdl
tests/conformance/invalid/aggregate-without-group.mdl
tests/conformance/invalid/invalid-join-predicate.mdl
tests/conformance/invalid/protobuf-reservation-reuse.mdl
```

Add governance broadening and orphaned registry ID tests only after verifying current compiler behavior and CLI contract.

### Expected outcomes manifest

Create:

```text
tests/conformance/invalid/expected.yaml
```

For each fixture store the stable expectation available from current CLI:

```yaml
missing-key.mdl:
  exit: 1
  code: SEM
  contains: "@key"
```

If structured diagnostics provide exact codes, prioritize code over prose. If not, use one minimal stable substring.

### Test runner

Create:

```text
tests/conformance/test_invalid_fixtures.py
```

The test MUST prove each fixture fails for its intended reason. A generic parse failure is not acceptable for a fixture intended to test semantic validation.

### Acceptance

```bash
pytest -q tests/conformance/test_invalid_fixtures.py
```

---

## Task 3.3 — Deferred fixtures

### Goal

Lock in explicit behavior for upstream-deferred capabilities without relying on them.

### Create fixtures for currently reported deferred capabilities

At minimum:

```text
tests/conformance/deferred/composite-keys.mdl
tests/conformance/deferred/workspace-registry.mdl
tests/conformance/deferred/workspace-peers.mdl
tests/conformance/deferred/consumer.mdl
tests/conformance/deferred/subscription.mdl
tests/conformance/deferred/materialisation.mdl
tests/conformance/deferred/binding-opaque-content.mdl
```

Some deferred capabilities are output semantics rather than source fixtures. Cover these with tests instead:

- ClickHouse secondary indexes are absent/deferred;
- nominal semantic identity beyond supported targets;
- projection event-operation compatibility comparison;
- model lifecycle status if not represented in grammar.

### Test

Create:

```text
tests/conformance/test_deferred_capabilities.py
```

For syntax that parses with warnings, assert the warning/category. For grammar-level non-support, assert the current explicit failure. Do not pretend all deferred capabilities behave identically.

### Acceptance

```bash
pytest -q tests/conformance/test_deferred_capabilities.py
```

Update capability coverage manifest.

---

# Phase 4 — Compatibility fixtures

## Task 4.1 — Model compatibility evolution

### Create

```text
compat/baseline-v1/
compat/additive-v2/
compat/breaking-v3/
```

Each directory must be a minimal standalone workspace, not a copy of the entire product if unnecessary.

Use one or two representative models, ideally Patient and Invoice.

### Required cases

`baseline-v1` -> `additive-v2`:

- add optional field;
- add deprecation metadata if compatible;
- preserve existing required fields.

`additive-v2` -> `breaking-v3`:

- remove/rename field;
- change type or nullability;
- add required field;
- change enum incompatibly.

### Tests

Create:

```text
tests/conformance/test_model_compatibility.py
```

Run real `modelable diff` or current compatibility command. Assert:

- additive path exits success;
- breaking path exits failure;
- report contains expected categories.

### Acceptance

```bash
pytest -q tests/conformance/test_model_compatibility.py
make compat
```

---

## Task 4.2 — Protobuf and gRPC compatibility

### Create

```text
compat/protobuf-safe/
compat/protobuf-breaking/
compat/grpc-read-index-change/
```

Each scenario should contain `old/` and `new/` workspaces if that matches the current CLI shape.

### Protobuf-safe case

Demonstrate deletion/evolution with correct `reserved protobuf` declarations where supported.

### Protobuf-breaking case

Demonstrate a target-wire incompatibility such as illegal number/name reuse or incompatible target type change according to current upstream rules.

### gRPC case

Change read index metadata so `validate-compat --target grpc` returns the current upstream classification for required read rebuild.

### Tests

Create:

```text
tests/conformance/test_target_compatibility.py
```

Run:

```bash
modelable validate-compat --from <old> --to <new> --target protobuf
modelable validate-compat --from <old> --to <new> --target grpc
```

Assert exit codes and stable result classifications.

### Acceptance

```bash
pytest -q tests/conformance/test_target_compatibility.py
```

---

# Phase 5 — Generate every implemented target

## Task 5.1 — Unified generation script

### Create

```text
scripts/generate-all.py
```

### Behavior

1. Run `modelable capabilities --format json`.
2. Select every target with status `implemented`.
3. Remove/recreate `generated/<target>/` safely.
4. Run `modelable compile model --target <target> --out generated/<target>`.
5. Capture stdout/stderr per target.
6. Fail if any implemented target fails.
7. Write `generated/manifest.json` containing:
   - Modelable version;
   - optional upstream commit SHA;
   - target list;
   - generated file inventory;
   - SHA-256 per file.
8. Never commit `generated/manifest.json`.

Use subprocess argument arrays, not shell-string interpolation.

### Update Makefile

`make generate` invokes the script.

### Tests

Create a small test that mocks only filesystem logic if needed, but the important test is the real integration invocation.

### Acceptance

```bash
make clean
make generate
python -m json.tool generated/manifest.json >/dev/null
```

All current implemented targets must appear.

---

## Task 5.2 — Artifact structural validation

### Create

```text
tests/integration/test_generated_artifacts.py
scripts/validate-generated.py
```

Prefer pytest for assertions and a script wrapper for Makefile/CI.

### Validate by target

#### JSON Schema

- every JSON file parses;
- schemas validate under Draft 2020-12 meta-schema where applicable;
- representative Patient request/reply schemas accept valid synthetic JSON and reject an invalid required-field case;
- expected Modelable metadata extensions are present on representative artifacts.

#### Markdown

- files exist for representative model/projection;
- Patient/Reporting docs contain version/field metadata;
- reporting projection contains lineage section/table.

#### SQL Postgres

Structural parsing may be minimal here; real application is Task 8.1.

#### SQL ClickHouse

Structural parsing may be minimal here; real application is Task 8.2.

#### dbt YAML

- parse every YAML file;
- assert top-level structure expected by current emitter;
- optionally add dbt parse later if generated output can be embedded cleanly.

#### FHIR

- parse JSON;
- `resourceType == StructureDefinition` for profiles;
- assert Patient/Observation/Encounter representative profile identity/base fields;
- verify at least one Modelable classification/lineage extension if current emitter promises it.

#### OpenMetadata

- parse;
- representative output contains domain/owner/classification/lineage metadata.

#### OpenLineage

- parse;
- representative projection has schema and column-lineage facets according to current emitter contract.

#### ODCS

- parse emitted YAML/JSON;
- assert contract identity/version/schema fields.

#### Protobuf/gRPC

File parsing and `protoc` happen in Task 7.5.

### Acceptance

```bash
make generate
pytest -q tests/integration/test_generated_artifacts.py
```

---

## Task 5.3 — Determinism gate

### Create

```text
scripts/check-determinism.py
```

### Behavior

For each implemented target:

1. generate into temp directory A;
2. generate into temp directory B;
3. compare relative file sets;
4. compare bytes SHA-256;
5. report exact mismatched files;
6. fail on any unexplained difference.

Do not compare `.modelable/registry.db` unless its determinism is an upstream public contract relevant to this suite. Focus on target output directories.

If a target legitimately includes documented nondeterministic data, first verify upstream documentation/tests, then implement the narrowest normalization possible and document it beside the code.

### Update Makefile

`make determinism` invokes script.

### Acceptance

```bash
make determinism
```

---

## Task 5.4 — Deterministic import/interchange and non-AI CLI surface

### Goal

The Modelable CLI has real, deterministic command surface beyond `validate`/`resolve`/`lineage`/`diff`/`compile` that this plan has not previously exercised: schema import/interchange, external-source drift tracking, and graph export. None of these are reported by `modelable capabilities --format json` (that manifest only covers `target`/`sql_dialect`/`model_kind`/`annotation`/`deferred_feature`), so the capability-coverage gate in Task 1.3 cannot catch drift here on its own — this task exists specifically to close that blind spot.

Do not confuse these with the AI-assisted commands (`update`, `chat` mutation turns, `suggest-projection`) that SPEC.md §2 excludes as a required deterministic gate. `generate --from` has both an AI path (freeform natural-language prompt) and a fully deterministic import path (`--format json-schema|sql|dbt|fhir|odcs`, no provider required) — only the deterministic import path belongs in this task.

### Create

```text
tests/conformance/import/
tests/integration/test_cli_surface.py
```

### Required coverage

1. **`generate --from` deterministic import**: round-trip at least two formats already produced by this repo's own `make generate` output — for example import a generated `json-schema` artifact and a generated `odcs` document back into a fresh `.mdl` file with `--output`, and assert the result parses/validates and preserves `x-modelable`/`customProperties` metadata (PII, classification, owner, key) per the current CLI contract. Do not import third-party schemas found online; use this repository's own generated artifacts as fixtures so the test has no external network dependency.
2. **`attach`**: attach an existing canonical model version to one external source format (dbt `schema.yml` is the natural fit given Task 2.x already produces one) and assert the command reports no drift when the source matches, and reports the expected additive/breaking `change_kind` when the source is deliberately mutated in a copied fixture.
3. **`spec add` / `spec status` / `spec diff`**: track one external source under `.modelable/specs.yml` in a disposable test workspace and assert `spec status --json` reports `clean` and, after mutating the copied fixture, `drifted`.
4. **`graph export`**: export the canonical workspace graph and assert the output is valid JSON containing the expected domain/model/projection identities; exercise `--focus` on one reference.
5. **`codegen formats` / `codegen types --format <x>`**: assert the reported format list matches the targets reported as implemented by `capabilities --format json`, and that `codegen types` returns a non-empty type mapping for at least one representative target.
6. **`transform <ref> --to <target> --explain`**: run once against a representative model version and assert the explanation output is non-empty; this is a thin smoke test, not a duplicate of Task 5.1/5.2's real compile-target coverage.

Use copied/temp fixtures for anything that writes files (`attach`, `spec sync --write`, `generate --output`). Never mutate canonical `model/` files from this test suite.

### Acceptance

```bash
make generate
pytest -q tests/integration/test_cli_surface.py
```

---

# Phase 6 — Product-consumed generated TypeScript

## Task 6.1 — Bootstrap React application

### Create under `apps/web/`

Use Vite React TypeScript.

Required dependencies:

- React;
- React DOM;
- React Router;
- TanStack Query;
- Vitest;
- Testing Library;
- Playwright added at repo or web level.

Do not add a large UI framework unless it materially reduces implementation complexity.

### Generated type integration

Choose one deterministic mechanism:

- configure TS path alias directly to `generated/typescript`; or
- copy/link generated TypeScript into `apps/web/src/generated` during build.

Prefer direct generated source consumption if it works cleanly with Vite/tsc.

No generated files committed.

### Minimal UI

Create routes/placeholders:

```text
/
/patients
/patients/:id
/schedule
/analytics
```

At this task, static placeholders are enough, but app build must import at least one generated Patient type so generated TS compilation is part of the build.

### Tests

- web unit test renders shell;
- TypeScript compiler sees generated model type;
- production build succeeds after `make generate`.

### Acceptance

```bash
make generate
cd apps/web
npm ci
npm test -- --run
npm run build
```

---

# Phase 7 — Generated language probes

## Task 7.1 — Rust generated package build

Before API work, prove generated Rust alone builds.

### Create

```text
tests/integration/test_rust_codegen.py
```

If Modelable multi-package Rust emits Cargo manifests, run `cargo test` or `cargo check` on each generated package/workspace.

Verify:

- registered semantic newtype exposes stable ID if current emitter promises it;
- model exposes schema version/content signature constants if current emitter promises them;
- at least one cross-package reference compiles.

### Acceptance

```bash
make generate
pytest -q tests/integration/test_rust_codegen.py
```

---

## Task 7.2 — C# probe

### Create

```text
probes/csharp/ModelableShowcase.Probe.csproj
probes/csharp/Program.cs or tests
```

Configure generated C# sources into the project without copying them into git.

Probe must:

- compile generated patient/billing/edge types;
- instantiate representative types;
- serialize at least one with `System.Text.Json` if generated shape supports it.

### Acceptance

```bash
make generate
dotnet test probes/csharp
```

If a console probe is simpler and no test framework is needed:

```bash
dotnet run --project probes/csharp
```

Prefer an actual test project for CI diagnostics.

---

## Task 7.3 — Java probe

### Create

A minimal Gradle or Maven project under `probes/java/`. Prefer Gradle wrapper if repository policy accepts wrapper files; otherwise Maven may reduce bootstrap complexity.

Probe must compile generated Java records/classes and perform one serialization or equality/construction test.

Use a supported Java LTS version, preferably 21 unless generated code requires another version.

### Acceptance

```bash
make generate
./probes/java/gradlew -p probes/java test
```

or documented Maven equivalent.

---

## Task 7.4 — Python and Go probes

### Python

Create:

```text
probes/python/pyproject.toml
probes/python/test_generated.py
```

Add generated Python directory to import path deliberately in test config. Instantiate and serialize representative generated dataclasses.

### Go

Create:

```text
probes/go/go.mod
probes/go/generated_test.go
```

Reference generated sources through module/package layout supported by current emitter. Avoid copying generated files into git.

### Acceptance

```bash
make generate
cd probes/python && uv run pytest -q
cd probes/go && go test ./...
```

---

## Task 7.5 — Protobuf and gRPC compile probes

### Requirements

Install/pin `protoc` in bootstrap/CI.

Generate protobuf and gRPC outputs, then compile every emitted `.proto` graph with the correct include roots.

If Modelable supports `--descriptor-set`, also invoke it in a separate target-specific test and verify descriptor files exist and are non-empty.

Inspect schema/service manifests and assert:

- schema identity;
- semantic type metadata;
- index/read index metadata where expected;
- reservations in evolved fixtures.

### Create

```text
tests/integration/test_protobuf_codegen.py
```

### Acceptance

```bash
make generate
pytest -q tests/integration/test_protobuf_codegen.py
```

---

## Task 7.6 — Unified probe target

Update `make probes` to run:

- Rust generated build;
- TypeScript web typecheck/build;
- C#;
- Java;
- Python;
- Go;
- Protobuf/gRPC.

### Acceptance

```bash
make probes
```

---

# Phase 8 — Databases from generated DDL

## Task 8.1 — PostgreSQL schema application

### Create

```text
docker-compose.yml
scripts/apply-postgres-ddl.sh or .py
tests/integration/test_postgres_generated_schema.py
```

### Compose service

Add PostgreSQL with:

- explicit major version;
- local-only development port;
- healthcheck;
- synthetic development credentials;
- named volume;
- isolated network.

### DDL application

Use generated `sql-postgres` output. Determine deterministic file order. Do not rewrite SQL semantics.

If generated SQL emits independent table files with dependency constraints, ordering script may topologically/order filenames only. It must not change column definitions.

### Round-trip tests

Using PostgreSQL directly:

- verify expected generated tables exist;
- verify patient/appointment/invoice representative columns and SQL types;
- insert a synthetic row into each product persistence table;
- read it back;
- verify generated secondary indexes exist for selected tables.

Use an actual DB client library in test code, not shell greps.

### Acceptance

```bash
docker compose up -d postgres
make generate
pytest -q tests/integration/test_postgres_generated_schema.py
```

---

## Task 8.2 — ClickHouse schema application

### Add Compose service

Pin ClickHouse version and add healthcheck/local-only port.

### Create

```text
scripts/apply-clickhouse-ddl.sh or .py
tests/integration/test_clickhouse_generated_schema.py
```

### Tests

- apply generated ClickHouse DDL;
- verify representative reporting tables;
- insert synthetic aggregate/report rows;
- query them back;
- assert the showcase does not require generated ClickHouse secondary indexes while upstream capability is deferred.

### Acceptance

```bash
docker compose up -d clickhouse
make generate
pytest -q tests/integration/test_clickhouse_generated_schema.py
```

---

# Phase 9 — Rust API product

## Task 9.0 — Verify upstream OpenAPI Phase A/B status (required checkpoint)

### Goal

`UPSTREAM_POLICY.md` §10 mandates this check before any HTTP API contract work begins, but earlier phases of this plan do not need it. Do not skip straight to Task 9.1 without running this task — the API's request/reply contract is meant to come from generated OpenAPI, not from hand-written Axum route structs, and that is only possible once upstream Modelable exposes it.

### Steps

1. Run `modelable capabilities --format json` and `modelable compile --help`; confirm whether `openapi` now appears as an implemented target.
2. If implemented, run `modelable compile ./model --target openapi --out generated/openapi` and confirm the output contains non-empty `paths` (Phase B), not only `components.schemas` with `paths: {}` (Phase A only).
3. If either layer is still missing, stop showcase API work. Follow `UPSTREAM_POLICY.md` §1 and §9: reproduce the need upstream, verify against `ktjn/modelable@main`, and track status against `ktjn/modelable#352` (or its successor if renumbered) until Phase B lands. Use `MODELABLE_REF=<branch-or-sha> make acceptance` against a candidate upstream branch to verify a fix before it merges.
4. Record the verified state (implemented / Phase A only / missing) in the PR or commit description for Task 9.1 so later agents do not re-verify from scratch unnecessarily.

### Acceptance

Task 9.1 may not begin until this task confirms full Phase A + Phase B OpenAPI generation is available on the pinned or canary Modelable ref being used for implementation.

---

## Task 9.1 — Bootstrap Axum API and generated Rust dependency

### Create under `apps/api/`

A Rust crate/workspace using:

- axum;
- tokio;
- serde/serde_json;
- sqlx PostgreSQL;
- tracing;
- health endpoints.

Reference generated Rust package(s) by local path produced by `make generate`.

The API build MUST fail if generated Rust contracts no longer compile.

### Endpoints

Initial:

```text
GET /health
GET /ready
```

`/ready` checks PostgreSQL and ClickHouse connectivity.

### Acceptance

```bash
make generate
cargo test --manifest-path apps/api/Cargo.toml
```

---

## Task 9.2 — Patient API

### Implement

```text
POST /api/patients
GET  /api/patients
GET  /api/patients/:id
```

Use generated Patient request/reply/current types at API boundaries.

Persistence writes to generated Patient DB table.

### Rules

- IDs server-generated if Modelable request projection excludes server fields;
- timestamps server-generated;
- synthetic search by name/email only;
- no authentication yet; access annotations are contract metadata, not runtime auth implementation for this showcase.

### Tests

Rust integration tests against PostgreSQL:

- create patient;
- fetch patient;
- list/search;
- duplicate/invalid request behavior;
- JSON shape matches generated schema for representative responses where practical.

### Acceptance

```bash
cargo test --manifest-path apps/api/Cargo.toml patient
```

---

## Task 9.3 — Scheduling API

Implement:

```text
POST  /api/appointments
PATCH /api/appointments/:id
POST  /api/appointments/:id/cancel
GET   /api/schedule?date=...
```

Use generated request/reply types and generated SQL tables.

Tests:

- booking;
- reschedule;
- cancel;
- daily practitioner schedule;
- patient appointment lookup.

Do not implement complex conflict resolution unless needed to exercise an index/query. A simple no-overlap validation is sufficient if implemented.

---

## Task 9.4 — Clinical and billing API

Implement:

```text
POST /api/encounters
POST /api/encounters/:id/observations
POST /api/invoices
POST /api/invoices/:id/payments
GET  /api/patients/:id/summary
```

Use generated contracts.

`PatientSummary` endpoint should reflect a real multi-domain aggregation. It may be composed by SQL/API logic from current state rather than Modelable runtime materialisation. Preserve Modelable projection semantics in field mapping.

Tests cover full API happy path.

---

## Task 9.5 — Analytics write/query path

When appointment/invoice/payment events occur, write enough data to ClickHouse to drive:

```text
GET /api/analytics/clinic
```

The endpoint returns at least:

- appointments per day;
- billed total;
- paid total;
- one practitioner aggregate.

The analytics table schema MUST come from generated ClickHouse output.

Do not implement Modelable subscriptions/materialisation. Application code owns synchronization explicitly.

---

## Task 9.6 — OpenAPI contract generation and consumption

### Goal

Task 9.0 confirmed upstream OpenAPI Phase A + Phase B are available. This task makes the showcase actually consume the generated contract, per `UPSTREAM_POLICY.md` §5 (read that section for full detail; this task tracks it in the dependency graph and file-ownership table rather than restating it).

### Required

1. Add `openapi` to `scripts/generate-all.py`'s target loop (Task 5.1) so it is generated by `make generate` into disposable `generated/openapi/`.
2. Independently validate the generated document with a standard OpenAPI 3.1 parser/validator, separate from whatever validation Modelable's own test suite performs.
3. Expose the generated contract to developers — a static docs route or a local Swagger UI/Scalar viewer is sufficient; do not hand-write the document it serves.
4. Add HTTP contract tests asserting the running Axum API's actual request/response shapes conform to the generated OpenAPI paths/operations for the endpoints built in Tasks 9.2-9.5.
5. Add `openapi` to the Task 5.3 determinism gate.
6. Add `target:openapi` (or its final capability key) to `tests/conformance/capability-coverage.yaml` classified as `product`.

### Acceptance

```bash
make generate
python -m json.tool generated/openapi/*.json >/dev/null
pytest -q tests/integration -k openapi
cargo test --manifest-path apps/api/Cargo.toml
```

### Acceptance Phase 9

```bash
docker compose up -d postgres clickhouse
make generate
cargo test --manifest-path apps/api/Cargo.toml
```

---

# Phase 10 — React product workflows

## Task 10.1 — Patient pages

Implement:

- patient list/search;
- create patient form;
- patient detail page;
- generated TypeScript request/reply types in API client.

Avoid generic form abstraction. Keep product code obvious.

Tests:

- form validation;
- API request mapping;
- detail rendering.

---

## Task 10.2 — Schedule and encounter pages

Implement:

- daily schedule page;
- appointment create/reschedule/cancel;
- encounter start/complete;
- observation entry.

The UI may use a simple list/table/calendar-day layout. Do not spend implementation budget on drag-and-drop or advanced calendar controls.

---

## Task 10.3 — Billing and analytics pages

Implement:

- invoice creation;
- payment action;
- patient billing summary;
- analytics page from ClickHouse-backed endpoint.

### Acceptance Phase 10

```bash
cd apps/web
npm test -- --run
npm run build
```

---

# Phase 11 — Docker product assembly

## Task 11.1 — Containerize API and web

### Add

```text
apps/api/Dockerfile
apps/web/Dockerfile
```

Prefer multi-stage builds.

Build stages MUST generate or consume Modelable artifacts deterministically. Choose one of these designs and document it:

1. top-level generation occurs before Docker build and generated directory is build context; or
2. dedicated generator stage installs Modelable and produces artifacts.

For `docker compose up --build` from a clean checkout, option 2 is usually stronger because no manual pre-step is required. If it makes build time unacceptable, Compose may run a one-shot generator service that API/web depend on.

Do not commit generated output to solve container build ordering.

### Compose dependencies

Services:

```text
postgres
clickhouse
generator (if used)
api
web
```

Use health/dependency conditions where Compose supports them. Application startup must handle databases becoming ready slightly later.

### Acceptance

```bash
docker compose down -v
docker compose up --build -d
docker compose ps
curl --fail http://localhost:<api-port>/health
curl --fail http://localhost:<web-port>/
```

Document exact ports in README.

---

# Phase 12 — Browser E2E

## Task 12.1 — Playwright harness

### Create

```text
tests/e2e/playwright.config.ts
tests/e2e/clinic.spec.ts
```

Use stable semantic selectors (`getByRole`, labels, test IDs only when needed).

### Required test

One test or a small serial flow MUST perform:

1. open product;
2. create fictional patient `Ada Example` or similarly obvious synthetic identity;
3. book appointment;
4. reschedule appointment;
5. start encounter;
6. add temperature and blood-pressure observation;
7. complete encounter;
8. create invoice;
9. record payment;
10. open patient summary and verify clinical + billing data;
11. open schedule and verify appointment state;
12. open analytics and verify aggregate reflects transaction.

Use unique run IDs to avoid collisions.

### Isolation

Each E2E run should either:

- start with fresh Compose volumes; or
- call a test-only reset endpoint available only under test configuration.

Prefer fresh disposable databases in CI.

### Update Makefile

`make e2e` starts required services, runs Playwright, and returns non-zero on failure.

### Acceptance

```bash
make e2e
```

---

# Phase 13 — LSP downstream protocol smoke

## Task 13.1 — Implement LSP JSON-RPC harness

### Create

```text
tests/integration/test_lsp_smoke.py
tests/fixtures/lsp-workspace/
```

Do not import internal LSP Python modules. Start the public executable/command.

Implement minimal Content-Length framed JSON-RPC client sufficient for tests.

### Test sequence

1. start server;
2. send `initialize`;
3. assert advertised capabilities;
4. `initialized`;
5. open a valid `.mdl` document;
6. wait for diagnostics and assert no errors;
7. request completion at a known location;
8. request hover on known field/model;
9. request definition;
10. request references;
11. request rename to a valid new identifier on a copied fixture;
12. request formatting if advertised;
13. shutdown/exit cleanly.

Add one invalid-document diagnostic test.

Use timeouts; never let CI hang indefinitely waiting for a notification.

### Acceptance

```bash
pytest -q tests/integration/test_lsp_smoke.py
```

---

# Phase 14 — Registry ID stability

## Task 14.1 — Add registry ID evolution tests

### Create

```text
tests/conformance/test_registry_ids.py
tests/fixtures/registry-ids/
```

Use copies/temp directories, never mutate canonical `model/registry-ids.lock` during tests.

### Cases

1. compile baseline: capture IDs;
2. compile again: unchanged;
3. add new `registry: true` semantic: new ID > current max;
4. remove old semantic: compile fails or reports orphan according to current CLI;
5. compile with explicit orphan allowance: old ID remains reserved and new type does not reuse it.

### Canonical lock check

Add a test that regenerating/compiling canonical model does not modify committed `model/registry-ids.lock`.

### Acceptance

```bash
pytest -q tests/conformance/test_registry_ids.py
```

---

# Phase 15 — Optional integration profiles

Do not start this phase until core `make acceptance` is stable.

## Task 15.1 — Protobuf/gRPC descriptor profile

If not already covered in Task 7.5, add explicit descriptor-set generation using current Modelable flags and `protoc`.

Make it deterministic and local.

---

## Task 15.2 — Apicurio publish/pull

Only implement if current Modelable capability reports this integration as supported.

### Add Compose profile

```text
apicurio
```

Use a pinned local Apicurio image.

### Test

- compile JSON Schema;
- publish one artifact using Modelable CLI;
- pull it into temp dir;
- compare logical identity/content according to upstream contract;
- no internet required after image/tool acquisition.

Expose as:

```bash
make integration-apicurio
```

Do not make ordinary `docker compose up` depend on it.

---

## Task 15.3 — Marquez/OpenLineage sync

Only implement if resource cost and upstream support make it reliable.

Use a Compose profile and local service. Send generated/design-time lineage through the real Modelable sync command, then query local service API to verify dataset/run/lineage receipt.

Keep it separate from core PR gate if startup cost is high.

---

## Task 15.4 — HL7 FHIR Validator smoke

Provide an optional script that validates representative generated Patient/Observation/Encounter profiles using the official validator CLI if available in CI cache/tool setup.

Do not download arbitrary binaries at runtime without checksum/version pinning.

---

# Phase 16 — CI and canary

## Task 16.1 — Core GitHub Actions workflow

### Create

```text
.github/workflows/ci.yml
```

### Jobs

#### `model`

Runs:

```bash
make bootstrap
make validate
make compat
```

Include valid/invalid/deferred/capability coverage tests.

#### `generate`

Runs:

```bash
make bootstrap
make generate
make determinism
```

Upload generated manifest/logs on failure if useful.

#### `languages`

Matrix or grouped jobs for:

- rust;
- typescript;
- csharp;
- java;
- python;
- go;
- protobuf-grpc.

Avoid one huge matrix if setup duplication dominates runtime; correctness is more important than aesthetic symmetry.

#### `databases`

Start PostgreSQL and ClickHouse, apply generated schemas, run integration tests.

#### `product`

Build/test API and web.

#### `e2e`

Build Compose stack and run Playwright.

Use artifacts/screenshots/traces on Playwright failure.

### Toolchain pinning

Pin:

- Python/uv;
- Node LTS;
- Rust stable or a known stable version;
- .NET LTS;
- Java LTS;
- Go stable minor/major policy;
- protoc;
- PostgreSQL/ClickHouse container tags.

Dependabot/Renovate may update later, but first implementation should be deterministic.

---

## Task 16.2 — Canary workflow

### Create

```text
.github/workflows/canary.yml
```

Support `workflow_dispatch` input:

```text
modelable_ref
```

The workflow MUST:

1. checkout showcase;
2. set `MODELABLE_REF`;
3. install Modelable from that upstream ref;
4. resolve/log exact upstream commit;
5. run the same core acceptance jobs or call a reusable workflow with the ref;
6. surface failure by stage/target.

If GitHub permissions allow cross-repository invocation from `ktjn/modelable`, later add `repository_dispatch` or reusable workflow integration. Do not block the initial implementation on that.

### Acceptance

Manually run canary once against upstream `main` and one explicit commit SHA.

---

# Phase 17 — Makefile completion and strict capability gate

## Task 17.1 — Finalize command façade

At this point every required Make target MUST be real.

Expected behavior:

```text
make bootstrap     install project tools/deps
make generate      generate all current implemented targets
make validate      strict model + conformance capability checks
make probes        downstream language/descriptor compilation
make compat        semantic + protobuf + grpc compatibility
make integration   generated artifact + DB + API integration tests
make e2e           Compose + Playwright
make determinism   double-generation hash comparison
make acceptance    all required non-optional gates
make clean         remove disposable build/test output
make up            docker compose up --build
make down          docker compose down
```

`make acceptance` ordering should fail fast enough to be useful:

```text
validate
compat
generate
determinism
probes
integration
product tests
e2e
lsp
```

CI may parallelize these even though local Make runs serially.

### Strict capability coverage

Enable strict mode in `scripts/check-capability-coverage.py`.

No `planned`/TODO entries remain.

Every upstream capability must have executable coverage or a justified exclusion.

### Acceptance

```bash
make clean
make acceptance
```

This is the final local definition of done.

---

# Phase 18 — Documentation hardening

## Task 18.1 — Update README with actual commands and architecture

Replace bootstrap placeholders with verified commands only.

README sections:

1. What this repo is.
2. What it tests.
3. Architecture diagram.
4. Quick start.
5. Run acceptance.
6. Run against Modelable upstream ref.
7. Generated artifact policy.
8. Synthetic-data warning.
9. Troubleshooting prerequisites.

Do not duplicate `SPEC.md` or this plan.

---

## Task 18.2 — Add coverage report command

Create:

```text
make coverage-report
```

It should print a compact table derived from upstream capabilities + local manifest:

```text
CATEGORY          CAPABILITY             STATUS        COVERAGE
model_kind        entity                 implemented   product
annotation        wire                   implemented   fixture
target            java                   implemented   probe
deferred_feature  subscriptions          deferred      deferred
```

Optional: generate `generated/capability-coverage.md` for CI artifacts. Do not commit it unless explicitly desired.

---

# Dependency graph for agents

Use this order:

```text
1.1 -> 1.2 -> 1.3
             |
             v
2.1 -> 2.2 -> 2.3 -> 2.4
                     |
                     +--> 3.1 -> 3.2 -> 3.3
                     |
                     +--> 4.1 -> 4.2
                     |
                     +--> 5.1 -> 5.2 -> 5.3 -> 5.4
                                  |
                                  +--> 6.1
                                  +--> 7.1..7.6
                                  +--> 8.1 -> 8.2
                                           |
                                           v
                                      9.0 -> 9.1 -> 9.2 -> 9.3 -> 9.4 -> 9.5 -> 9.6
                                                               |
                                                               v
                                                        10.1 -> 10.2 -> 10.3
                                                               |
                                                               v
                                                            11.1
                                                               |
                                                               v
                                                            12.1

2.x + generated workspace --> 13.1 LSP
2.x + registry semantics  --> 14.1 registry IDs
core stable               --> 15.x optional integrations
all core tasks            --> 16.1 -> 16.2 -> 17.1 -> 18.x
```

Tasks 3.x, 4.x, 6.1, 7.x, and 13.1 may be parallelized after the canonical model is stable enough, but agents must avoid simultaneous conflicting edits to `model/*.mdl`, `Makefile`, or shared CI files.

---

# File ownership guidance for parallel agents

If multiple agents implement in parallel, assign ownership:

| Area | Primary files |
|---|---|
| Model language | `model/**`, `tests/conformance/**` |
| Generator | `scripts/generate-all.py`, `scripts/check-determinism.py` |
| Capability coverage | `tests/conformance/capability-coverage.yaml`, `scripts/check-capability-coverage.py` |
| Import/interchange & CLI surface | `tests/conformance/import/**`, `tests/integration/test_cli_surface.py` |
| Web | `apps/web/**` |
| API | `apps/api/**` (includes OpenAPI consumption per Task 9.6) |
| Language probes | `probes/**`, relevant integration tests |
| Databases | `docker-compose.yml`, DB scripts/tests |
| E2E | `tests/e2e/**` |
| LSP | `tests/integration/test_lsp_smoke.py`, LSP fixtures |
| CI | `.github/workflows/**` |

Only one agent at a time should make structural changes to `Makefile` and `docker-compose.yml`. Other agents should provide requested target/service requirements rather than racing edits.

---

# Common implementation traps

## Do not handwrite generated contracts

Bad:

```text
apps/api/src/models/patient.rs
apps/web/src/types/patient.ts
```

when those merely duplicate Modelable output.

Good:

```text
apps/api depends on generated Rust crate
apps/web imports generated TypeScript interface
```

Infrastructure-specific wrappers are allowed when they do not duplicate contract semantics.

## Do not commit generated output to make builds easy

Fix build orchestration instead.

The exception is `model/registry-ids.lock`, which is source-controlled allocation state.

## Do not assume deferred runtime behavior

A `subscription` or `materialisation` block parsing does not mean this showcase may rely on runtime execution. Application code owns data movement until upstream capability status changes.

## Do not grep for success when a real compiler/database exists

Prefer:

```text
dotnet test
cargo test
go test
protoc
PostgreSQL connection + catalog query
ClickHouse connection + query
JSON Schema validator
Playwright
```

over checking generated text contains a token.

Text assertions are acceptable only for metadata that has no stronger executable validator.

## Do not overfit to human diagnostics

Prefer exit codes, structured JSON, diagnostic codes, manifest classifications, and machine-readable fields.

## Do not normalize nondeterminism without proof

If hashes differ, investigate upstream output first. Normalization requires a documented upstream reason.

## Do not make healthcare claims

This is a technical showcase. Use fictional data and simple workflows only.

---

# Final verification checklist

Before declaring the implementation complete, run from a clean checkout/worktree:

```bash
make bootstrap
make clean
make acceptance
docker compose down -v
docker compose up --build -d
```

Then manually verify:

- web page loads;
- create patient works;
- booking works;
- encounter + observation works;
- invoice + payment works;
- patient summary works;
- analytics page shows data.

Then verify upstream canary:

```bash
MODELABLE_REF=main make clean acceptance
```

Finally run:

```bash
make coverage-report
```

There must be no unclassified upstream capabilities and no remaining implementation TODO markers in required acceptance paths.

The implementation is finished only when the repository satisfies every item in `SPEC.md` section **Definition of done** and `make acceptance` passes against the pinned release.