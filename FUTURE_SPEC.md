# Modelable Showcase — Future Acceptance Specification

**Status:** future specification; non-blocking until promoted  
**Repository:** `ktjn/modelable-showcase`  
**Upstream:** `ktjn/modelable`  
**Current governing specification:** [`SPEC.md`](SPEC.md)

This document defines future downstream acceptance requirements for Modelable capabilities that are not yet part of the current showcase Definition of Done.

It is intentionally separate from `SPEC.md`:

- `SPEC.md` remains the authoritative specification for what the showcase MUST implement now.
- This document describes the next acceptance surface that SHOULD become executable as the corresponding upstream capabilities land.
- A requirement here MUST NOT fail normal acceptance merely because upstream still reports the capability as deferred or unimplemented.
- Once an upstream capability is sufficiently implemented and stable, the corresponding section of this document SHOULD be promoted into `SPEC.md`, executable fixtures, and the capability/CLI coverage gates.

The governing future product promise is:

> Change a model, and Modelable should tell every affected application what changes, why it changes, and what work is required — then generate as much of that work as can be proven safe.

The future showcase therefore needs to validate more than generated artifacts inside one workspace. It must validate evolution across independently changing application boundaries.

---

## 1. Future purpose

The current clinic product answers:

> Can a real application be built from Modelable-generated contracts and artifacts?

The future acceptance scenarios MUST additionally answer:

> Can several independently evolving applications use Modelable as their contract, dependency, consequence, migration, and transformation system without requiring synchronized releases?

The future showcase SHOULD retain the clinic product as the realistic single-application path and add isolated, intentionally adversarial multi-application scenarios for cross-boundary evolution.

The showcase MUST continue to prefer meaningful downstream consequences over syntax acceptance. A future feature is covered only when the strongest relevant consequence has been proven: generated code compiles, transformations preserve values, migrations preserve stored data, dependency snapshots support offline builds, impact analysis identifies the correct consumer, or a deliberate failure is reported with a useful causal explanation.

---

## 2. Future repository structure

Add a future scenario axis beside the clinic application rather than turning the clinic into a large microservice system.

Target shape:

```text
.
├── model/                         # current rich clinic workspace
├── apps/                          # current runnable clinic product
├── probes/                        # target/toolchain probes
├── compat/                        # isolated compatibility fixtures
├── scenarios/
│   └── application-evolution/
│       ├── patient-service/
│       ├── scheduling-service/
│       ├── billing-service/
│       ├── reporting-service/
│       ├── upstream-registry/
│       └── fixtures/
└── tests/
    └── future/
```

The application-evolution scenario MUST NOT require every logical consumer to be a separately deployed runtime service. Small Modelable workspaces plus focused executable consumers are preferred. Runtime services should only be introduced when runtime behavior is itself the feature under test.

---

## 3. Multi-application evolution scenario

The primary future scenario MUST model independent ownership and intentionally lagging consumers.

Suggested ownership:

```text
patient-service
  owns Patient@1, Patient@2, Patient@3
  publishes PatientReply
  publishes PatientEvent

scheduling-service
  consumes an older PatientReply contract

billing-service
  consumes Patient and PatientEvent
  persists a local projection

reporting-service
  consumes a newer PatientReply and derived reporting projections
```

At least one scenario MUST have consumers on different versions at the same time, for example:

```text
producer:   Patient@3
scheduling: PatientReply@1
billing:    Patient@2 / PatientEvent@1
reporting:  PatientReply@3
```

A producer upgrade MUST NOT assume consumers upgrade atomically.

The scenario MUST prove that an upstream change can identify consequences for each consumer independently.

Example expected result:

```text
change Patient@3 -> Patient@4

scheduling-service
  no_action

billing-service
  storage_migration
  regenerate

reporting-service
  regenerate

legacy-consumer
  consumer_update
  breaking
```

---

## 4. Registry snapshot lifecycle

When Modelable gains deterministic external contract resolution, the showcase MUST validate registry snapshots as durable build inputs.

The lifecycle MUST cover:

1. resolving external contracts;
2. pinning the resolved versions and content identities;
3. persisting the transitive reachable dependency closure;
4. rebuilding without access to the original provider;
5. explicit updates rather than implicit refresh during normal compile;
6. verification of snapshot integrity and provenance.

A representative acceptance flow SHOULD be equivalent to:

```bash
modelable registry resolve

# Remove or make the provider unavailable.
mv ../provider ../provider.offline

modelable validate
modelable compile
modelable impact
```

The final three commands MUST succeed from the resolved local state when no update has been requested.

Required cases:

- exact version resolution from a range;
- deterministic transitive closure;
- byte-stable snapshot generation from identical inputs;
- same logical version with different content identity rejected;
- unused dependencies detectable and removable;
- historical checkout builds against its historical snapshot;
- newer provider versions do not silently change normal builds;
- explicit update changes the snapshot only when successful;
- failed update leaves the previous snapshot unchanged;
- provenance identifies where each resolved contract came from;
- content/signature verification detects tampering or accidental replacement.

Registry resolution MUST be testable without an external SaaS dependency in the default path.

---

## 5. Dependency snapshots as usage evidence

The future showcase MUST test the architectural assumption that explicit consumer declarations are not required merely to identify contract usage.

For a consumer workspace with access to many upstream contracts, the resolved usage/snapshot state SHOULD contain only the contracts reachable from the consumer's actual references plus required transitive dependencies.

Required cases:

```text
provider exposes 20 contracts
consumer directly/transitively uses 3
```

Then:

- changing an unused provider contract MUST NOT mark the consumer impacted;
- changing a directly used contract MUST identify the consumer;
- changing a transitively used field MUST identify the consumer and the complete dependency path;
- removing the last usage of a contract SHOULD allow it to be identified as unused/prunable;
- usage evidence MUST remain deterministic across clean builds.

The result SHOULD make a separate handwritten consumer inventory unnecessary for normal compile-time impact analysis.

---

## 6. Consequence analysis

Compatibility and consequence analysis are different acceptance surfaces.

Compatibility answers:

> Is the change allowed/safe under a compatibility policy?

Consequence analysis answers:

> What work must each affected application perform because of the change?

The future showcase MUST validate both.

The consequence vocabulary SHOULD include, or map clearly onto, concepts equivalent to:

```text
no_action
regenerate
recompile
consumer_update
storage_migration
data_backfill
projection_rebuild
event_replay
governance_review
breaking
```

Required scenario classes:

| Change | Expected consequence |
|---|---|
| documentation-only change | `no_action` |
| field used by generated client/types | `regenerate` |
| generated source signature changes | `recompile` and/or `regenerate` |
| computed projection logic changes | `projection_rebuild` |
| stored nullable field added | `storage_migration` |
| stored required field added with historical rows | `storage_migration` + `data_backfill` |
| event payload incompatible for a consumer | `consumer_update` / `breaking` |
| event-derived projection semantics change | `projection_rebuild` and, when required, `event_replay` |
| classification/access becomes more restrictive | `governance_review` |
| unused provider model changes | `no_action` for the consumer |

Consequences MUST be derived from dependency and semantic facts rather than inferred only from model names or target presence.

---

## 7. Causal impact paths

Impact output MUST explain why an application is affected.

For representative cases the showcase MUST assert a machine-readable causal path equivalent to:

```text
Patient.email
  -> PatientReply.email
  -> PatientApi.getPatient.response
  -> scheduling-service
```

and, for storage:

```text
Patient.dateOfBirth
  -> PatientDb.dateOfBirth
  -> postgres.patient_db.date_of_birth
  -> billing-service
```

The showcase SHOULD avoid golden-testing complete human prose. It SHOULD assert stable identifiers, node/edge categories, consequence categories, and source/target ownership.

When several independent paths exist, impact analysis SHOULD preserve enough structure to explain all material reasons without duplicating identical consequences unnecessarily.

---

## 8. Generated conversion helpers

When Modelable can generate conversions between models, projections, versions, events, API contracts, or storage representations, the showcase MUST test semantic behavior rather than only compilation.

Required conversion classes:

```text
direct field copy
renamed field with explicit lineage/mapping
optional -> optional
optional -> required with declared default
optional -> required without a safe default
model -> db projection
request -> model/domain input
model -> reply projection
model -> event projection
version N -> version N+1
```

Converters MUST be classified according to what can be proven, with categories equivalent to:

```text
total + reversible
total + non-reversible
partial/fallible
requires custom hook
impossible
```

The showcase MUST include non-invertible examples:

- `pick`/`omit` losing information;
- computed expressions;
- aggregation;
- joins;
- lossy type conversions.

Modelable MUST NOT synthesize a reverse conversion when reversibility cannot be proven.

For unresolved business logic, generated code SHOULD call a stable explicit user hook rather than requiring edits to generated files.

Representative behavioral acceptance:

```text
Patient
  -> PatientDb
  -> database round trip
  -> PatientReply
```

The test MUST compare meaningful values and null/default behavior, not merely prove that the generated mapper compiles.

Language-specific idioms MAY differ, for example `From`/`TryFrom` in Rust and normal mapping functions or factories elsewhere, but semantic results MUST remain consistent.

---

## 9. Defaults and value-origin semantics

Future Modelable semantics MUST distinguish concepts that currently risk being conflated under a generic default.

The showcase MUST eventually exercise distinct forms equivalent to:

```text
input default
constructor/domain default
serialization default
database default
migration backfill
server-generated value
```

A field MUST be able to have different behavior at these different boundaries without accidental propagation.

Required cases include:

- input omitted but constructor value supplied;
- request omitted and server generates value;
- serialization omission/default does not silently become a database default;
- database default applies to new rows but does not falsely claim historical rows were backfilled;
- migration backfill is required for existing rows when appropriate;
- generated converters correctly account for the declared default origin.

---

## 10. Real database evolution

Fresh-schema application is not sufficient for the future migration/evolution feature set.

The showcase MUST add stateful database evolution tests:

```text
create schema from V1
insert representative V1 rows
upgrade model to V2
generate/inspect required consequences
apply migration or approved generated migration
verify existing rows
verify new writes
verify generated readers/writers
```

Required PostgreSQL scenarios SHOULD include:

- nullable column addition;
- required column addition with safe backfill;
- required column addition without safe backfill, requiring manual intervention;
- database default;
- server-generated field;
- rename when lineage proves identity;
- type widening;
- type narrowing rejected or classified as manual migration;
- index addition/removal;
- reference/foreign-key evolution;
- value-object / JSONB representation evolution;
- projection/table rebuild when semantic derivation changes.

Equivalent ClickHouse evolution SHOULD be tested where Modelable provides migration/rebuild semantics appropriate to ClickHouse.

The migration suite MUST preserve seeded V1 data unless data loss is explicitly part of the tested breaking/manual scenario.

---

## 11. Configuration inheritance and explainability

When Modelable gains broader defaulting and target configuration, the showcase MUST validate deterministic precedence.

The intended precedence SHOULD be equivalent to:

```text
built-in
  < workspace
  < domain
  < model/projection
  < field
  < CLI
```

At least one fixture MUST exercise all available levels for the same effective setting.

A command equivalent to:

```bash
modelable config explain patient.Patient@3 --target postgres
```

SHOULD expose both:

- the effective value;
- the source/origin of that value.

Required cases:

- inherited workspace default;
- domain override;
- model override;
- field-level exception;
- CLI override;
- conflicting settings resolved by documented precedence;
- invalid override diagnosed rather than silently ignored;
- effective configuration remains deterministic.

Configuration tests MUST focus on user-observable behavior and explain output, not internal merge implementation.

---

## 12. Auto-projection policy inheritance

The clinic model SHOULD become a realistic consumer of inherited auto-projection defaults once that capability lands.

Instead of repeating equivalent blocks for every model version, future configuration SHOULD allow normal defaults such as:

```text
db
request
reply
event
```

with local exceptions.

The showcase MUST test:

- inheritance across multiple entity versions;
- explicit opt-out;
- per-model exclusion;
- annotation-based exclusion such as `@server` from request;
- per-model event operation subset;
- override without losing unrelated inherited defaults;
- expanded canonical projections are inspectable;
- downstream lineage/compatibility/consequence logic behaves the same whether the projection was explicit or produced from inherited policy.

The acceptance goal is not merely syntax reduction. The feature SHOULD measurably remove repetitive configuration while preserving explicit inspectable semantics.

---

## 13. API evolution

Generated OpenAPI acceptance MUST expand from "does the current API match" to API evolution across consumer versions.

Required evolution cases SHOULD include:

- optional request property added;
- required request property added;
- reply property added/removed;
- path parameter added/removed/changed;
- query parameter added;
- query parameter becoming required;
- response status added/removed;
- error contract changed;
- operation removed;
- operation identifier changed;
- path changed.

API consequences MUST connect to consuming applications.

Representative causal path:

```text
PatientReply changed
  -> PatientApi.getPatient.response changed
  -> generated TypeScript client/contracts changed
  -> web consumer requires regeneration or update
```

If Modelable adds higher-level API convention/resource profiles, the showcase MUST prove that convenience syntax expands deterministically into inspectable explicit API IR. Convention syntax MUST NOT hide the actual operation contract from impact analysis.

---

## 14. Event lifecycle and event-sink contracts

The `event-sink`/outbox capability SHOULD be exercised as a real downstream contract without requiring Modelable to become a broker/runtime platform.

Representative flow:

```text
model mutation
  -> generated event projection
  -> generated event-sink/outbox contract
  -> local persisted event
  -> downstream consumer deserializes event
```

Required future cases:

- envelope stability across payload versions;
- producer and consumer on different event versions;
- event operation subset (`created`, `updated`, `deleted`, or equivalent);
- event field addition/removal/type change;
- impact path from source model to event consumer;
- incompatible event change requiring `consumer_update`;
- changed event-derived projection requiring `projection_rebuild`;
- `event_replay` consequence when historical events can rebuild the projection and semantics require it.

A local database-backed outbox or in-process reader is sufficient. Kafka or another broker MUST NOT be required for default acceptance unless broker behavior itself becomes part of Modelable's supported contract.

---

## 15. Rich language semantics that affect evolution

The following future language features SHOULD be promoted into executable showcase coverage as they land because they materially improve impact, conversion, API, event, and storage reasoning:

- first-class value constraints;
- named version-aware enums;
- discriminated unions;
- model lifecycle status;
- richer semantic/nominal type support across targets.

These features MUST be tested as evolution semantics, not only parser syntax.

Examples:

- tightening a constraint and identifying affected consumers/data;
- additive versus breaking enum evolution;
- union variant addition/removal;
- lifecycle deprecation/removal consequences;
- nominal type mismatch that is structurally identical but semantically incompatible.

---

## 16. Plugin and extension acceptance

If Modelable introduces trusted compiler plugins or typed namespaced annotations, the showcase MUST validate a minimal third-party extension path.

The extension mechanism SHOULD be able to contribute well-defined capabilities such as:

- annotation schema/validation;
- compatibility significance;
- target-specific type mapping;
- conversion hook generation;
- artifact emission;
- diagnostics.

Required properties:

- plugins are explicit trusted build dependencies;
- arbitrary code is not executed merely because an `.mdl` file contains an unknown annotation;
- plugin identity/version is visible in deterministic build metadata;
- missing plugin fails clearly;
- plugin output participates in determinism checks;
- plugin-generated semantic dependencies participate in impact analysis where applicable.

A single small fixture plugin is sufficient. The showcase MUST NOT become a general plugin marketplace or plugin-framework test suite.

---

## 17. Future requirement tracking

Capabilities described here may exist before they are advertised through `modelable capabilities`, so capability discovery alone cannot protect this roadmap from disappearing.

Until promoted, future requirements SHOULD be tracked explicitly in this document and, where useful, lightweight non-blocking fixtures under:

```text
tests/future/
```

or equivalent.

Potential future acceptance groups include:

```text
registry snapshots
cross-application impact
consequence actions
conversion generation
migration/backfill semantics
configuration inheritance
auto-projection inheritance
API evolution
event lifecycle
constraints
enums
unions
plugin API
```

A future fixture MUST NOT pretend an unimplemented capability passes. It may document intended input/output, expected diagnostic, or a skipped/non-gating test tied to the upstream capability status.

---

## 18. Promotion rules

A future section SHOULD move into `SPEC.md` when all of the following are true:

1. the upstream capability has a stable deterministic CLI/compiler surface suitable for downstream testing;
2. the capability is not merely experimental syntax with intentionally ignored semantics;
3. the showcase can test it without depending on external SaaS in the default acceptance path;
4. expected downstream consequences can be asserted meaningfully;
5. any required target/runtime support is sufficiently implemented to avoid a permanently fake probe.

On promotion:

- add executable product/probe/fixture coverage;
- update `tests/conformance/capability-coverage.yaml` when the capability is exposed there;
- update the CLI coverage list when a new command is involved;
- remove any obsolete deferred-boundary assertion;
- update `IMPLEMENTATION_PLAN.md` with an implementation slice;
- add or update `MODELABLE_FEATURE_REQUESTS.md` only when actual upstream friction/request tracking remains relevant;
- add discovered defects to `UPSTREAM_FINDINGS.md` according to `UPSTREAM_POLICY.md`.

Promotion SHOULD happen incrementally. The entire future spec does not need to become mandatory at once.

---

## 19. Future Definition of Done

The future cross-application acceptance surface is complete when the following can be demonstrated end-to-end:

1. Multiple independently versioned Modelable workspaces consume contracts owned by another workspace.
2. External contract resolution produces deterministic, verifiable local snapshots.
3. A clean build can validate, compile, and analyze impact offline from those snapshots.
4. Consumers can intentionally lag behind the provider without forcing synchronized upgrades.
5. A model change identifies only the actually affected applications.
6. Impact output contains machine-readable causal paths from changed field/model through projection/API/event/storage edges to the consumer.
7. Compatibility and required actions are reported separately.
8. Consequences distinguish regeneration, recompilation, consumer updates, storage migration, data backfill, projection rebuild, event replay, governance review, and breaking/manual work where applicable.
9. Generated conversion helpers compile and preserve representative values.
10. Non-reversible or unsafe conversions are rejected or routed through explicit user hooks rather than guessed.
11. Database evolution is tested from populated V1 state to V2+, not only against empty fresh schemas.
12. Default/value-origin semantics correctly distinguish input, construction, serialization, database, backfill, and server generation.
13. Configuration inheritance is deterministic and explainable to the user.
14. Auto-projection defaults remove repetitive configuration while expanding into inspectable canonical semantics.
15. API evolution propagates consequences to real downstream consumers.
16. Event evolution propagates consequences to real downstream consumers and can identify rebuild/replay requirements.
17. Rich constraints/enums/unions/lifecycle semantics participate in compatibility and consequence analysis once upstream supports them.
18. Trusted plugin extensions can participate without compromising deterministic or explicit builds.
19. No permanent patch layer modifies generated artifacts after Modelable emits them.
20. A Modelable upstream PR affecting any of these features can run this scenario suite as a downstream canary before release.

The final principle is:

> The showcase should test Modelable as a change-and-consequence compiler, not only as a model parser and artifact generator.
