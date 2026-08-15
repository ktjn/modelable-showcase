# Modelable Showcase Specification

**Status:** implementation specification  
**Repository:** `ktjn/modelable-showcase`  
**Upstream:** `ktjn/modelable`

This document is the single source of truth for *what* is required and *what "done" means* — every requirement, acceptance criterion, and the Definition of Done (§25) live here and only here. [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) sequences the *how* and *in what order*; it cross-references section numbers here rather than restating requirements, and it must not be treated as adding to or relaxing anything stated in this document. [`UPSTREAM_POLICY.md`](UPSTREAM_POLICY.md) governs process for upstream gaps and points back to §25 for the OpenAPI-specific acceptance items it once duplicated. If any of the three ever disagree, this document governs.

## 1. Purpose

`modelable-showcase` is a downstream acceptance application for Modelable.

It MUST be all of the following at the same time:

1. A small product that a human can build, start, and use.
2. A realistic consumer of generated Modelable artifacts.
3. A broad language and compiler conformance suite.
4. A compatibility regression suite covering schema evolution.
5. A canary that can run against a released Modelable version or an arbitrary upstream commit/branch.

The repository MUST NOT become a copy of Modelable's own unit tests. The primary value is proving that generated contracts survive downstream compilation, database creation, serialization, API execution, and browser workflows.

The product is a fictional outpatient clinic named **Modelable Clinic**.

Healthcare is intentionally used because it naturally exercises PII, classification, access restrictions, versioned records, events, analytics, monetary values, cross-domain references, and FHIR-oriented artifacts.

No real patient data may be committed or used. All fixture data MUST be synthetic and obviously fictional.

## 2. Non-goals

The showcase MUST NOT:

- implement Modelable's deferred runtime subscriptions or materialisation engine;
- duplicate the Modelable parser/compiler inside this repository;
- hand-maintain DTOs that duplicate Modelable-generated product contracts;
- treat generated artifacts as source-of-truth;
- test the internal implementation details of Modelable;
- require external SaaS services for the default local or pull-request test path;
- use Modelable's LLM features as a required deterministic acceptance gate;
- use real medical data or claim clinical correctness.

Modelable's own Playground UI, VS Code UI, and provider-specific LLM behavior remain upstream responsibilities. This repository may smoke-test public CLI/LSP surfaces but is not a UI test suite for the Modelable repository itself.

## 3. Product definition

The running product MUST support these user-visible flows:

1. Register a patient.
2. Search and open a patient.
3. Book an appointment for a practitioner.
4. Reschedule and cancel an appointment.
5. Start and complete an encounter.
6. Record observations such as blood pressure, weight, and temperature.
7. Create an invoice with line items.
8. Record a payment.
9. View a patient summary combining patient, scheduling, clinical, and billing information.
10. View a daily practitioner schedule.
11. View simple clinic analytics such as appointments per day and billed/paid totals.

A complete browser E2E test MUST exercise the happy-path journey:

`patient -> appointment -> encounter -> observation -> invoice -> payment -> summary`

The product is intentionally small. Features exist to prove Modelable contracts, not to become a full electronic health record system.

## 4. Runtime architecture

Use the following architecture unless an implementation slice documents a compelling incompatibility with a generated artifact:

```text
React + TypeScript web application
              |
              | JSON/HTTP
              v
Rust + Axum API
       |             |
       v             v
 PostgreSQL      ClickHouse
 product state   analytics
```

### 4.1 Web

Use:

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Playwright for E2E

The web application MUST consume Modelable-generated TypeScript types for API contracts. It MUST NOT define parallel handwritten interfaces for generated request/reply models.

### 4.2 API

Use:

- Rust stable
- Axum
- Tokio
- SQLx for PostgreSQL
- a maintained ClickHouse Rust client
- Serde

The API MUST consume Modelable-generated Rust types for domain/API contracts where the Rust target can represent them.

The API MAY define infrastructure-specific types for HTTP errors, SQL rows that cannot cleanly map to generated contracts, pagination, authentication stubs, and database connection configuration. These types MUST NOT duplicate domain contract shapes merely for convenience.

### 4.3 PostgreSQL

PostgreSQL stores product state.

Persistence tables MUST originate from Modelable-generated `sql-postgres` output for selected `db` projections. The repository MUST NOT contain a second handwritten canonical schema for the same tables.

If runtime migration glue is needed, it MAY wrap or order generated DDL, but MUST NOT silently rewrite field types or columns.

### 4.4 ClickHouse

ClickHouse stores reporting/analytics projections.

The tables used by the analytics page MUST be created from Modelable-generated `sql-clickhouse` output.

Modelable runtime materialisation is currently deferred upstream, so the showcase application owns the code that writes/rebuilds analytics rows. This boundary MUST remain explicit.

ClickHouse secondary indexes MUST NOT be required by showcase acceptance while upstream reports them as deferred.

### 4.5 Local execution

The primary developer command MUST be:

```bash
docker compose up --build
```

After startup:

- the web UI MUST be reachable on one documented localhost port;
- the API MUST expose `/health` and `/ready`;
- PostgreSQL MUST have a healthcheck;
- ClickHouse MUST have a healthcheck;
- containers MUST start from a clean checkout without manually generated files.

A non-containerized developer flow SHOULD also exist for faster web/API iteration.

## 5. Repository layout

The target layout is:

```text
.
├── model/
│   ├── workspace.mdl
│   ├── patient.mdl
│   ├── scheduling.mdl
│   ├── clinical.mdl
│   ├── billing.mdl
│   ├── audit.mdl
│   ├── reporting.mdl
│   └── registry-ids.lock
├── apps/
│   ├── web/
│   └── api/
├── probes/
│   ├── csharp/
│   ├── java/
│   ├── python/
│   └── go/
├── compat/
│   ├── baseline-v1/
│   ├── additive-v2/
│   ├── breaking-v3/
│   ├── protobuf-safe/
│   ├── protobuf-breaking/
│   └── grpc-read-index-change/
├── tests/
│   ├── conformance/
│   │   ├── valid/
│   │   ├── invalid/
│   │   ├── deferred/
│   │   └── capability-coverage.yaml
│   ├── integration/
│   └── e2e/
├── generated/
├── scripts/
├── docker-compose.yml
├── Makefile
├── SPEC.md
└── IMPLEMENTATION_PLAN.md
```

`generated/` MUST be disposable build output and ignored by git except where an individual compatibility fixture explicitly requires committed golden data. `model/registry-ids.lock` MUST be committed because it is durable allocation state.

## 6. Model domains

### 6.1 `patient`

Owns patient identity and contact information.

Required definitions:

- semantic `PatientId`
- value `Address`
- value `ContactDetails`
- entity `Patient`
- multiple `Patient` versions
- auto projections for the current version
- indexes for patient search

The domain MUST exercise:

- `uuid(7)` where supported for new IDs;
- strings;
- dates;
- optional fields;
- arrays;
- nested objects or named values;
- defaults;
- `@key`;
- `@pii`;
- `@classification`;
- `@owner`;
- `@deprecated`;
- `@server`;
- `@wire` on at least one non-critical field;
- access blocks;
- additive and breaking evolution.

Required evolution story:

- `Patient @1`: simple name/contact representation;
- `Patient @2 (additive)`: add at least one optional field and deprecate a prior field;
- `Patient @3 (breaking)`: demonstrate a real incompatible reshape in compatibility fixtures, not necessarily the product's active version.

The running product SHOULD use the newest non-breaking/current contract suitable for the implementation. Breaking fixture versions exist to prove failure behavior and need not be the live product schema.

### 6.2 `scheduling`

Required definitions:

- semantic `AppointmentId`
- value `TimeRange` or equivalent
- aggregate/entity `Appointment`
- event `AppointmentStatusChanged` or equivalent
- auto projections
- indexes supporting patient/day, practitioner/day, and status lookup

Exercise:

- `timestamp`;
- `date`;
- `time`;
- `duration`;
- enums;
- refs to patient and practitioner identifiers/models;
- optional fields;
- defaults;
- secondary indexes;
- server-generated timestamps.

### 6.3 `clinical`

Required definitions:

- semantic `EncounterId`
- semantic types with at least one chain
- entity/aggregate `Encounter`
- entity/event `Observation`
- value `Diagnosis`
- value/object for measurement metadata

Exercise a broad type surface naturally across this domain and dedicated valid-edge fixtures:

- `int`;
- signed fixed-width integer;
- unsigned fixed-width integer;
- `float`;
- `decimal(p,s)`;
- `bool`;
- `uuid` and `uuid(7)`;
- `timestamp`;
- `date`;
- `time`;
- `duration`;
- `binary`;
- `binary(N)`;
- `array<T>`;
- `map<K,V>`;
- `ref<...>`;
- inline enum;
- object;
- `json`.

Not every extreme type must pollute the live product. Unnatural but legal combinations belong under `tests/conformance/valid/`.

FHIR-specific projections MUST exist for `Patient`, `Observation`, and `Encounter` source models so the `fhir-profile` target exercises its hardened source-model paths.

### 6.4 `billing`

Required definitions:

- semantic `InvoiceId`
- aggregate `Invoice`
- value `InvoiceLine`
- event `PaymentReceived`
- auto projections
- indexes
- multiple versions used by compatibility fixtures

Exercise:

- decimal money values;
- arrays of value objects;
- enums;
- defaults;
- refs;
- exact version references;
- version ranges;
- Protobuf reservations in an evolved contract.

### 6.5 `audit`

Required definition:

- event `AuditEntry`

Exercise:

- event model kind;
- timestamp;
- actor/subject references;
- classification;
- access metadata;
- binary signature/digest representation;
- arbitrary JSON metadata.

Audit data MUST use fictional values and MUST NOT contain secrets.

### 6.6 `reporting`

This domain is projection-heavy and SHOULD contain few or no canonical entities.

Required projections:

- `PatientSummary`
- `DailySchedule`
- `PatientClinicalSummary`
- `OutstandingInvoices`
- `PractitionerRevenue`
- `MonthlyClinicStats`

Across these projections exercise:

- direct mapping (`<-`);
- computed fields (`=`);
- CEL boolean logic;
- CEL arithmetic;
- ternary expressions;
- deterministic string helpers;
- `coalesce` or equivalent null-handling helper;
- joins;
- left joins;
- `where`;
- `group by`;
- `count`;
- `sum`;
- `avg`;
- `min`;
- `max`;
- `countif`;
- `count_distinct` if supported by the pinned capability baseline;
- exact source versions;
- version ranges;
- `pick`;
- `omit`;
- annotation selectors such as `@pii`/`@classification`;
- lineage across multiple domains.

The running product MUST consume at least `PatientSummary`, `DailySchedule`, and one financial aggregate in an actual endpoint/page.

## 7. Modelable language coverage

### 7.1 Model kinds

The repository MUST have successful examples of every upstream model kind currently reported as implemented by `modelable capabilities`.

At the time this specification was written, the known core set is:

- entity
- aggregate
- event
- value

The test suite MUST discover the authoritative capability list from the Modelable binary rather than trusting this prose forever.

### 7.2 Annotations

The repository MUST cover every annotation reported as implemented by `modelable capabilities`.

Known current annotations include:

- key
- pii
- classification
- deprecated
- owner
- server
- wire
- pit cutoff
- latest before
- latest only
- custom annotations

Annotations that do not fit the live clinic model naturally SHOULD be exercised by focused valid fixtures.

### 7.3 Semantic types

Exercise:

- primitive-backed semantic type;
- `registry: true` semantic type;
- chained semantic type;
- cross-domain semantic reference;
- domain-qualified semantic reference;
- same-named semantic types in different domains requiring qualification;
- stable `registry-ids.lock` allocation;
- orphan handling in a dedicated negative/compatibility fixture;
- semantic cycle rejection.

### 7.4 Indexes

Exercise:

- primary index declaration;
- secondary index;
- compound secondary key where legal;
- sort columns;
- descending sort;
- unique secondary index;
- invalid field rejection;
- index evolution visible to gRPC compatibility.

### 7.5 Auto projections

Exercise all implemented auto projection kinds:

- db
- request
- reply
- event

Also exercise:

- field exclusion;
- annotation exclusion;
- event operation subsets;
- `@server` exclusion from request projections.

### 7.6 Selection and lineage

Exercise:

- `pick` by explicit field;
- `omit` by explicit field;
- annotation-based selection;
- selection plus additional body fields;
- duplicate output rejection;
- direct lineage;
- computed lineage;
- aggregate lineage;
- cross-domain lineage.

### 7.7 CEL

The live product SHOULD use common CEL constructs. Exhaustive operator/function edge cases belong in focused conformance fixtures.

Required positive coverage:

- precedence between arithmetic/comparison/logical operators;
- parentheses;
- unary negation where valid;
- booleans;
- strings;
- numeric literals;
- ternary;
- deterministic scalar function calls;
- field access;
- aggregate functions in grouped projections.

Required negative coverage:

- unknown alias;
- unknown field;
- type mismatch;
- non-deterministic/rejected functions such as random/UUID/current-user equivalents;
- aggregate outside `group by`;
- invalid predicate type.

## 8. Capability-driven coverage contract

Create `tests/conformance/capability-coverage.yaml` as the machine-readable coverage manifest.

It MUST map every capability returned by:

```bash
modelable capabilities --format json
```

to one of:

- `product`: exercised by the running application;
- `probe`: exercised by compiling/validating an emitted artifact;
- `fixture`: exercised by focused positive/negative conformance input;
- `deferred`: upstream says the capability is deferred and this repository asserts the deferred diagnostic/boundary;
- `excluded`: explicitly not a downstream-testable surface, with a mandatory reason.

Discover the manifest's own top-level categories from the binary rather than assuming a fixed set; at specification time they are `target`, `sql_dialect`, `model_kind`, `annotation`, and `deferred_feature`. `sql_dialect` is easy to under-cover because it currently has only two entries (`postgres`, `clickhouse`) and is not called out anywhere else in this document — both MUST still receive explicit manifest entries.

Target vocabulary that is only accepted inside `.mdl` `generate {}` blocks but has no `compile --target` implementation behind it does not appear in `capabilities --format json` and therefore requires no manifest entry — do not fabricate placeholder keys for it. Confirm with `modelable compile --help` before treating something as a gap here.

This manifest mechanism covers `target`/`sql_dialect`/`model_kind`/`annotation`/`deferred_feature` drift only. It does NOT cover drift in the broader CLI *command* surface (`spec`, `attach`, `graph export`, `generate --from` import paths, `transform`, `codegen`, etc.) — that surface is covered separately by §15.

A CI test MUST fail when:

1. upstream reports a new implemented capability with no coverage entry;
2. a capability marked `deferred` becomes implemented but remains classified as deferred locally;
3. a capability marked `product`, `probe`, or `fixture` has no corresponding executable test ID/path;
4. a capability disappears without the manifest being deliberately updated.

This mechanism is the primary defense against the showcase silently becoming stale as Modelable evolves.

## 9. Generated target coverage

The showcase MUST compile every code-generation target that the pinned Modelable binary reports as `implemented`.

Known implemented targets at specification time are:

- `json-schema`
- `markdown`
- `typescript`
- `csharp`
- `java`
- `python`
- `rust`
- `go`
- `sql-postgres`
- `sql-clickhouse`
- `dbt-yaml`
- `fhir-profile`
- `openmetadata`
- `openlineage`
- `odcs`
- `protobuf`
- `grpc`

Do not hard-code this list as the sole CI source. Discover targets from `modelable capabilities --format json`; use the list above as the initial expected baseline.

### 9.1 Product-consumed targets

At minimum, these MUST be consumed by the running product or its real infrastructure:

- TypeScript
- Rust
- PostgreSQL SQL
- ClickHouse SQL
- JSON Schema

FHIR profiles SHOULD participate in a real export/validation flow once the core product is operational.

### 9.2 Probe-consumed language targets

Create minimal downstream projects for:

- C#
- Java
- Python
- Go

Each probe MUST compile/import generated code and instantiate or serialize representative difficult contracts. Merely checking that a file exists is insufficient.

Rust and TypeScript are already product-consumed and need no duplicate probe unless useful for isolated regression diagnosis.

### 9.3 Artifact targets

Validate emitted artifacts beyond file existence:

- JSON Schema: parse and validate representative valid/invalid instances using a standards-compliant validator.
- Markdown: verify expected documents and key metadata/lineage sections; optionally lint.
- PostgreSQL SQL: apply to a fresh PostgreSQL instance.
- ClickHouse SQL: apply to a fresh ClickHouse instance.
- dbt YAML: YAML parse plus a minimal dbt parse project if generated shape permits it without fabricating semantics.
- FHIR profile: parse as JSON and validate core StructureDefinition invariants; provide an opt-in HL7 validator gate.
- OpenMetadata: parse JSON and assert domain/owner/classification/lineage presence.
- OpenLineage: parse event JSON and assert dataset/schema/column-lineage facets on representative projections.
- ODCS: parse YAML/JSON as emitted and assert contract identity/schema fields.
- Protobuf: run `protoc` on generated schemas and inspect schema manifests.
- gRPC: run `protoc` on generated services/messages and inspect service manifests.

## 10. Multi-package generation

The workspace MUST use Modelable `package {}` configuration to exercise explicit package grouping where supported.

Initial Rust package groups:

- `clinic-core`: patient + scheduling
- `clinical-core`: clinical + audit
- `billing-core`: billing + reporting where dependency direction remains acyclic

The exact grouping MAY change if the package dependency graph would be cyclic. The accepted design MUST keep packages independently buildable and MUST include at least one real cross-package generated Rust reference.

A CI test MUST build the generated multi-crate Rust output.

Do not require non-Rust package manifests until upstream reports that behavior as implemented.

## 11. Compatibility suite

Compatibility is a first-class showcase function, not incidental test data.

Required fixture sets:

```text
compat/baseline-v1/
compat/additive-v2/
compat/breaking-v3/
compat/protobuf-safe/
compat/protobuf-breaking/
compat/grpc-read-index-change/
```

Tests MUST cover:

- additive field addition accepted;
- required field addition rejected/breaking as appropriate;
- field removal;
- type change;
- nullability change;
- enum evolution;
- source version change;
- projection lineage change visibility;
- classification/access change visibility;
- Protobuf reserved name/number safe evolution;
- Protobuf field-number/name reuse rejection where supported;
- Protobuf target compatibility command;
- gRPC target compatibility command;
- gRPC read-index change producing the upstream-defined non-wire-compatible/rebuild classification.

Tests MUST assert exit status and stable machine-readable/category output where available. Avoid golden-testing complete human-readable prose.

## 12. Positive edge-case fixtures

`tests/conformance/valid/` exists for legal but awkward constructs that do not belong in the clinic product model.

Include focused fixtures for:

- numeric width boundaries including 128-bit forms;
- `binary(1)` and maximum legal fixed binary size;
- optional arrays;
- arrays of inline enums;
- legal map shapes;
- nested objects;
- `json`;
- deeply chained semantic types near a practical boundary without making CI slow;
- qualified semantic-name ambiguity resolution;
- difficult CEL precedence;
- ternaries;
- string escaping;
- defaults;
- version ranges;
- pinned/content-signature references where locally testable;
- Protobuf reservations;
- annotation selectors.

Each fixture MUST document which behavior it proves through its filename and/or adjacent test case.

## 13. Negative fixtures

`tests/conformance/invalid/` MUST contain one-purpose invalid files. Each fixture MUST fail for the intended reason, not because of an unrelated earlier parse error.

Initial cases:

- duplicate key / unsupported composite key;
- missing key;
- key on invalid model kind;
- unknown model reference;
- unknown semantic type;
- semantic cycle;
- ambiguous semantic type;
- invalid index field;
- duplicate secondary index name;
- breaking change declared additive;
- unresolved version range;
- duplicate projection output from selection + body;
- empty/invalid `pick` where prohibited;
- invalid CEL function;
- CEL type mismatch;
- aggregate without grouping;
- invalid join predicate;
- Protobuf reservation reuse;
- illegal governance/classification broadening if enforced by current compiler behavior;
- orphaned registry ID without the explicit allow flag.

Tests SHOULD assert diagnostic codes/categories and source locations when upstream exposes stable structured diagnostics.

"CEL type mismatch" is not currently enforceable: verified against both the pinned `modelable==1.7.0` release and upstream `main` that comparing incompatible CEL operand types (e.g. `stringField > 5`) validates cleanly with no diagnostic. The `CEL003`/`CEL004` diagnostic codes are reserved in the code but have no implementation behind them, strongly suggesting this was planned and never finished rather than intentionally out of scope. `tests/conformance/invalid/` accordingly has 17 fixtures, not 18 — 16 from this list plus `empty-pick.mdl` for "empty/invalid pick", with CEL type mismatch the one documented gap. Per `UPSTREAM_POLICY.md` Sec 1 this belongs on the list of gaps to eventually fix upstream (Case A: Modelable is incomplete); do not add a downstream fixture that pretends to test enforcement that does not exist.

## 14. Deferred capability fixtures

`tests/conformance/deferred/` MUST prove explicit behavior for syntax/capabilities that upstream currently reports as deferred.

Known current deferred areas include:

- composite keys;
- ClickHouse secondary index emission;
- model lifecycle status;
- nominal semantic identity in targets beyond the currently supported nominal targets;
- workspace registry configuration;
- workspace peers;
- consumer declarations;
- subscriptions;
- materialisation;
- opaque binding content beyond implemented fields;
- projection event-operation compatibility comparison.

For parseable-but-deferred syntax, assert that the expected deferred warning is emitted and that the product does not rely on the ignored semantics.

The CLI entry points for federated-registry behavior — `registry init`, `registry peer add`, `registry graph`, `registry sync`, `dependents`, and `lineage verify` — are themselves currently deferred functionality per upstream documentation, even though some exist as CLI subcommands. Cover their current (non-)behavior with the same deferred-fixture discipline as `workspace-registry`/`workspace-peers`/`consumer-declarations` rather than leaving them untested merely because they are commands rather than `.mdl` syntax.

When upstream changes a capability to implemented, the capability coverage gate MUST force this repository to reclassify and add a real implementation test.

## 15. CLI acceptance surface

The deterministic test suite MUST exercise the user-facing CLI paths used by downstream consumers:

- `capabilities --format json`
- `validate --strict`
- `compile`
- `resolve`
- `lineage`
- `diff`
- `validate-compat` for supported targets
- `docs` or the equivalent markdown compile target
- `inspect ... --auto` if present in the pinned version
- formatting/check command(s) exposed by the pinned version
- `graph export`, including `--focus`
- `codegen formats` and `codegen types --format <x>`
- `generate --from` using only its deterministic import paths (`--format json-schema|sql|dbt|fhir|odcs` against this repository's own generated artifacts), never the freeform natural-language path
- `attach`
- `spec add` / `spec status` / `spec diff` / `spec sync --preview`
- `transform ... --to <target> --explain`

Tests MUST discover command availability from the actual pinned binary when command names are version-sensitive. A removed/renamed stable command should fail the showcase until deliberately adapted.

This list is intentionally broader than what `modelable capabilities --format json` reports (see §8) — several real, deterministic commands (`graph export`, `spec`, `attach`, `codegen`, the import path of `generate`, `transform`) live entirely outside that manifest's five categories, so this hand-maintained list is the only drift check they get. Keep it in sync with `docs/cli-reference.md` in the pinned/canary Modelable checkout when commands are added, renamed, or removed upstream.

Explicitly out of scope for this section: `create`, `scenario`, `describe`, `docs-index`, `docs-eval`, `docs-ask`, `models`, and the AI-gated paths of `generate`/`update`/`chat`/`suggest-projection` (per §2, LLM features are never a required deterministic gate). `chat`'s deterministic, provider-free read-only question mode (ownership, lineage, dependents, indexes, compatibility, validation) MAY be smoke-tested but is not required.

## 16. LSP smoke suite

Add a protocol-level smoke test for the public language server after core compilation works.

The test MUST start the real Modelable LSP process and exercise, using JSON-RPC/LSP rather than internal Python imports:

- initialize/shutdown;
- open workspace document;
- diagnostics;
- completion;
- hover;
- go-to-definition;
- references;
- rename;
- formatting, if advertised by server capabilities.

Use a small copied workspace fixture. Do not point the LSP mutation tests at the canonical `model/` files.

The LSP suite is a downstream protocol compatibility test, not exhaustive editor testing.

## 17. Registry IDs

`registry-ids.lock` is source-controlled state.

Tests MUST prove:

- first allocation is deterministic;
- repeated compile preserves IDs;
- adding a registered semantic type allocates a new ID without renumbering old IDs;
- deleting a registered semantic type produces orphan handling rather than silent reuse;
- explicit orphan allowance preserves the reserved ID.

Never regenerate `registry-ids.lock` from scratch in normal CI in a way that masks accidental renumbering.

## 18. Determinism

For each implemented target, generate into two clean directories from the same input and compare normalized file inventories and byte hashes.

Allowed nondeterminism MUST be documented per target and normalized only when upstream explicitly defines it as nondeterministic. Do not paper over unstable output by sorting/removing arbitrary content in showcase tests.

Generated artifact determinism is a required gate.

## 19. Integration profiles

### 19.1 Core/default

The default PR path MUST require only local containers/toolchains and MUST include:

- model validation;
- capability coverage;
- generation of every implemented target;
- language probes;
- PostgreSQL apply;
- ClickHouse apply;
- API tests;
- web tests;
- Playwright E2E;
- compatibility suite;
- determinism.

### 19.2 Optional upstream integrations

After the core showcase is stable, add separately invokable integration profiles for Modelable integrations that can run locally, such as:

- Apicurio publish/pull using a local Apicurio container;
- Marquez-compatible OpenLineage sync using a local service if resource cost is acceptable;
- Protobuf/gRPC descriptor generation with `protoc`;
- HL7 FHIR Validator smoke.

These MUST NOT make ordinary local product startup depend on registry/catalog services.

## 20. Upstream Modelable selection

The repository MUST support two modes.

### 20.1 Release mode

Use a pinned released Modelable version for reproducible normal development.

Store the version in exactly one obvious location and provide:

```bash
make modelable-version
```

or equivalent.

### 20.2 Canary mode

Allow CI/local tests against an arbitrary upstream git ref without editing product files:

```bash
MODELABLE_REF=<branch-tag-or-sha> make acceptance
```

The implementation SHOULD support installing Modelable directly from `ktjn/modelable` at that ref or checking out upstream in CI and installing the CLI from source.

The canary workflow MUST record the exact upstream commit SHA in test output/artifacts.

This is the most important downstream use case: a Modelable pull request should be testable against this repository before the upstream change is merged/released.

## 21. Test levels

The final repository MUST contain all of these levels:

### Level 1: source validation

- `modelable validate --strict`
- formatter/check stability
- capability coverage manifest

### Level 2: compiler semantics

- resolve
- lineage
- auto projection inspection
- compatibility/diff
- valid/invalid/deferred fixtures

### Level 3: artifact generation

- every implemented target generates successfully
- generated inventory is deterministic
- target-specific structural validation

### Level 4: downstream compilation

- TypeScript typecheck/build
- Rust build/test
- C# compile/test
- Java compile/test
- Python import/test
- Go compile/test
- Protobuf/gRPC `protoc`

### Level 5: infrastructure

- generated PostgreSQL DDL applies
- generated ClickHouse DDL applies
- real insert/read round trips

### Level 6: application integration

- API starts against generated schemas
- product CRUD/workflows pass
- generated JSON Schema validates request/reply fixtures

### Level 7: browser E2E

- Playwright runs the complete clinic journey

## 22. Make targets

The repository MUST expose a stable command façade so agents do not need to memorize tool-specific commands.

Required targets or equivalent scripts:

```text
make bootstrap
make generate
make validate
make probes
make compat
make integration
make e2e
make determinism
make acceptance
make clean
make up
make down
```

`make acceptance` MUST be the complete non-optional local gate and MUST be what CI runs, even if CI internally splits it into parallel jobs.

`make clean && make acceptance` MUST work from a clean checkout once required host toolchains are installed.

## 23. CI

GitHub Actions MUST include:

1. `model` job: validation, fixtures, compatibility, capability coverage.
2. `generate` job: all targets + determinism.
3. `languages` matrix: Rust, TypeScript, C#, Java, Python, Go, Protobuf/gRPC.
4. `databases` job: PostgreSQL + ClickHouse generated DDL and integration tests.
5. `product` job: API + web unit/integration build.
6. `e2e` job: complete Docker Compose product + Playwright.
7. `canary` workflow_dispatch/reusable path accepting `modelable_ref`.

Pin action major versions and toolchain versions where practical. Use dependency caches, but CI correctness MUST NOT depend on cache contents.

## 24. Security and data rules

- Never commit secrets.
- Use synthetic test identities only.
- No external telemetry in default tests.
- Bind database ports to localhost only for development.
- Use non-production credentials in Compose and mark them as such.
- Do not expose PostgreSQL/ClickHouse publicly in CI.
- Generated Markdown and metadata exports MUST be checked to ensure secrets from runtime configuration are not embedded.
- Treat generated output as untrusted build input until it has passed target-specific validation/compilation.

## 25. Definition of done

The repository is complete when all of the following are true:

1. `docker compose up --build` starts a usable clinic product from a clean checkout.
2. The browser happy-path clinic journey passes under Playwright.
3. The web app consumes generated TypeScript contracts.
4. The Rust API consumes generated Rust contracts.
5. PostgreSQL product tables are created from generated SQL.
6. ClickHouse analytics tables are created from generated SQL and drive at least one real page/query.
7. Every upstream target reported as implemented is generated and has meaningful validation.
8. Every implemented capability has an entry in the coverage manifest.
9. Every current deferred capability has an explicit boundary test or justified exclusion.
10. C#, Java, Python, and Go probes compile/import representative generated contracts.
11. Protobuf and gRPC artifacts compile with `protoc` and pass compatibility fixtures.
12. Compatibility tests include additive, breaking, Protobuf-safe/breaking, and gRPC read-index changes.
13. Positive, negative, and deferred fixture suites exist and prove edge behavior.
14. Registry semantic IDs are stable across repeated builds/evolution.
15. Generation is deterministic for all implemented targets.
16. A protocol-level LSP smoke test passes.
17. `make acceptance` passes locally from a clean generated state.
18. CI passes in pinned-release mode.
19. A manually supplied `MODELABLE_REF` can run the same downstream acceptance suite against an upstream Modelable commit.
20. OpenAPI is generated by Modelable, not handwritten or derived from the web/API framework.
21. The generated OpenAPI contains the product's real paths and operations, not only schemas.
22. The generated OpenAPI document passes an independent validator.
23. Running API contract tests prove the Axum implementation conforms to generated OpenAPI request/reply contracts.
24. OpenAPI generation is deterministic and included in the coverage manifest as `product`.
25. No permanent showcase patch layer exists for Modelable-generated artifacts (see `UPSTREAM_POLICY.md` §7).
26. Every general Modelable defect or missing capability encountered during implementation is either fixed upstream or explicitly documented as an intentional upstream limitation with a corresponding showcase boundary test.
27. The deterministic, non-AI-gated CLI surface listed in §15 — `graph export`, `codegen`, `attach`, `spec`, and the import path of `generate` — has passing coverage, not only the compiler/validation commands used earlier in this list.
28. The federated-registry CLI entry points (`registry ...`, `dependents`, `lineage verify`) have an explicit deferred-boundary test per §14, not silence.

Items 20-26 restate `UPSTREAM_POLICY.md` §11 verbatim as part of this single merged checklist; that document remains the authoritative process description for *how* to reach them, this list is the authoritative statement of *whether the repository is done*.

The governing principle is:

> A Modelable feature is not considered covered merely because Modelable accepts the `.mdl` syntax. The showcase must prove the strongest meaningful downstream consequence available: product behavior, generated-code compilation, real database application, artifact validation, compatibility result, or an explicit deferred diagnostic.
