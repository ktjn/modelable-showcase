# Modelable Feature Requests — Showcase-Driven Improvements

This document collects feature requests for the **Modelable** generator (upstream,
`https://github.com/ktjn/modelable`) derived from building the Modelable Showcase
(acceptance product in this repository, pinned to `modelable==1.8.0`).

Each request names the concrete friction the showcase hit, maps it to the
relevant task and/or `UPSTREAM_FINDINGS.md` entry, proposes a behavior, and gives
an acceptance hint. The requests are ordered roughly by impact on this project.

This log is maintained in lockstep with `UPSTREAM_FINDINGS.md` per
`UPSTREAM_POLICY.md` §13: new findings that imply a capability update this
document, and a finding that is fixed upstream updates the status of the FRs
that cite it in the same commit.

**v1.8.0 status note (2026-08):** the showcase's pin moved from `1.7.0` to
`1.8.0`, and every FR below shipped in that release (via
[#354](https://github.com/ktjn/modelable/pull/354),
[#355](https://github.com/ktjn/modelable/pull/355),
[#364](https://github.com/ktjn/modelable/pull/364),
[#365](https://github.com/ktjn/modelable/pull/365), and
[#366](https://github.com/ktjn/modelable/pull/366)). Most are fully implemented;
FR-4 and FR-11 are only partially implemented because new findings in v1.8.0's
output block full adoption. Status below is per-request and reflects the 1.8.0
reality, which the showcase's flip tests pin exactly.

| ID | Feature | Friction source | Status |
|----|---------|-----------------|--------|
| FR-1 | Emit `PRIMARY KEY`/`UNIQUE` from `@key` in generated DDL | Tasks 9.2/9.3 duplicate handling | Implemented in v1.8.0 (verified: `patient_id TEXT NOT NULL PRIMARY KEY`) |
| FR-2 | Server-generated key fields (IDs dropped from the request projection) | Tasks 9.2/9.3 | Implemented in v1.8.0 |
| FR-3 | Symmetric Rust serde attributes (`#[serde(default)]`) | Findings #34/#38 | Implemented in v1.9.1 (verified: exactly one `#[serde(default)]` per `Option` field) |
| FR-4 | Generated Rust compiles for every supported model | Findings #14/#26/#38/#39 | Implemented in v1.9.2 (verified: `cargo check` green on clinic/clinical/billing-core) |
| FR-5 | Legal ClickHouse rendering for optional arrays | Finding #25 | Implemented in v1.8.0 (verified: full clickhouse set applies) |
| FR-6 | Globally unique deterministic index names | Finding #24 | Implemented in v1.8.0 (verified: table-prefixed names) |
| FR-7 | Cwd-independent deterministic registry-id resolution | Task 9.0 OpenAPI probe | Implemented in v1.8.0 (verified: ledger at `model/registry-ids.lock`) |
| FR-8 | Ship `openapi` in a versioned release (with a real version string) | Task 9.0 | Implemented in v1.8.0 (verified: `modelable capabilities` includes openapi; `modelable --version` = 1.8.0) |
| FR-9 | Canonical, round-trippable `time`/`duration` serialization | Task 9.3 | Implemented in v1.8.0 (verified: chrono types in generated Rust) |
| FR-10 | Value objects as `jsonb` (or generated query operators) | Tasks 9.2/9.3 search/ordering | Implemented in v1.8.0 (verified: `contact JSONB NOT NULL` in DDL) |
| FR-11 | Foreign keys from `ref<>` in generated DDL | Tasks 9.2/9.3 | Partially implemented in v1.8.0 — FKs emitted but broken on new finding #27 |
| FR-12 | Official event-sink/outbox materialising event projections | Task 9.5 plan | Implemented in v1.8.0 (event-sink target ships) |
| FR-13 | A generated registry/contract module | Task 9.1 `/health` | Implemented in v1.8.0 (verified: `generated/registry/registry.json`) |

---

## FR-1 — Emit `PRIMARY KEY` / `UNIQUE` from `@key` in generated DDL

**Status:** Implemented in v1.8.0. Verified against the 1.8.0 regeneration:
`generated/sql-postgres/patient.PatientDb.v2.sql` emits `patient_id TEXT NOT NULL
PRIMARY KEY` and every generated table has its `@key` column set as `PRIMARY KEY`.
The API duplicate-handling path can now use `INSERT ... ON CONFLICT`.

**Friction.** Every generated SQL table has `@key` fields emitted only as
`TEXT NOT NULL` with no primary-key or unique constraint. The API therefore
cannot rely on the database to reject duplicates. Tasks 9.2 and 9.3 both had to
hand-implement a non-atomic check-then-insert (`SELECT 1 ... WHERE id = $1`,
then `INSERT`, return 409) because a naive insert would silently create
duplicate rows.

**Proposed behavior.** When an entity declares a key
(`@key` / `semantic`/`index { primary }`), emit `PRIMARY KEY` (or a
`UNIQUE` constraint when the key is not a simple single column) for that column
set in the generated DDL.

**Acceptance.** `patient.PatientDb.v2.sql` contains
`patient_id TEXT NOT NULL PRIMARY KEY` (or a table-level constraint); the
showcase can then implement create as an `INSERT ... ON CONFLICT DO NOTHING`
(+ check `rows_affected`) instead of a separate `SELECT`.

---

## FR-2 — Server-generated key fields (IDs dropped from the request projection)

**Status:** Implemented in v1.8.0. The request projection now excludes key fields
marked server-owned, so the generated request type omits the id and the API mints
it.

**Friction.** The generated `request` projection excludes `@server` fields but
not key fields, so `patientId` and `appointmentId` must be supplied by the
client (`SchedulingAppointmentRequestV1.appointment_id` is `AppointmentId`,
not an `Option`). The Task 9.2/9.3 plan expected server-generated IDs; instead
the showcase accepts client-chosen UUIDs and needs FR-1's duplicate handling on
top.

**Proposed behavior.** Allow a field (including a key field) to be marked
server-owned — e.g. by extending `@server` to key fields, or by a projection
option such as `request exclude [@key @server]` — so the generated request type
omits the id and the API mints it (uuid v4 / timestamp) itself.

**Acceptance.** With `@server` on `patientId`, `PatientPatientRequestV2` has no
`patient_id` field; the API generates it; FR-1's `ON CONFLICT` path becomes a
defensive edge case rather than the primary flow.

---

## FR-3 — Symmetric Rust serde attributes (`#[serde(default)]`)

**Status:** Implemented. #34 shipped fixed in **v1.9.0**; the regression it
introduced, [finding #38](UPSTREAM_FINDINGS.md#38) (duplicate `#[serde(default)]`),
was fixed in **v1.9.1** via #387. Verified against the **1.9.3** regeneration:
every `Option` field carries exactly one `#[serde(default)]` alongside
`skip_serializing_if`, so generated Rust types are lossless in both directions.

**Friction.** Generated Rust structs annotate every `Option` field with
`#[serde(skip_serializing_if = "Option::is_none")]` but no `#[serde(default)]`.
The serialized form of a generated type (with `None` optionals omitted) cannot
be deserialized back into the same type — the API reply JSON in Tasks 9.2/9.3
only round-trips if the consumer re-adds the missing keys explicitly. Tests had
to assert "set fields present, unset fields omitted" and "full JSON parses"
separately, and callers cannot treat the generated types as symmetric wire
types.

**Proposed behavior.** Emit `#[serde(default)]` (and keep
`skip_serializing_if`) on `Option` fields, so generated types are lossless in
both directions. Optionally expose a `deny_unknown_fields` toggle.

**Acceptance.** `serde_json::from_value::<PatientPatientReplyV2>(serde_json::to_value(&reply)?)`
succeeds; the showcase reply-shape tests collapse to a single round-trip check.

---

## FR-4 — Generated Rust compiles for every supported model

**Status:** Implemented. #14 shipped fixed in
[#355](https://github.com/ktjn/modelable/pull/355) (v1.8.0, `clinical-core` compiles),
#26 shipped fixed in **v1.9.0** (`billing-core` no longer errors on the missing
`From` impl), and the two regressions those fixes surfaced — #38 (duplicate
`#[serde(default)]`, fixed in v1.9.1 via #387) and #39 (cross-domain status-enum
`From` imports via `super::` in package mode, fixed in v1.9.2 via #389) — are
also resolved. Verified against the **1.9.3** regeneration: `cargo check` on all
three of `clinic-core`, `clinical-core`, and `billing-core` succeeds, so the
"every supported model compiles" acceptance criterion is met.

**Friction.** Finding #14: `compile --target rust` loses named-type resolution
for **optional array fields** specifically. On pinned 1.7.0 the generated
`clinical` and `billing` Rust packages do not compile, so the API crate
(`apps/api`) references only `patient` and `scheduling`. Every cross-domain
capability (Task 9.4 clinical/billing endpoints, Task 9.6 OpenAPI consumption)
is blocked on the fix landing upstream and being released.

**Proposed behavior.** Fix the Rust emitter for optional array fields and add a
compile-everything smoke test to the generator's own CI so a broken target
cannot be shipped again.

**Acceptance.** `cargo check` on the generated `clinic-core` crate for
`clinical`, `billing`, `patient`, `scheduling`, and `reporting` succeeds; the
showcase API can reference all generated packages.

---

## FR-5 — Legal ClickHouse rendering for optional arrays

**Status:** Implemented in v1.8.0. Verified against the 1.8.0 regeneration:
optional arrays are rendered as bare `Array(T)` (no `Nullable` wrapper), so the
full `generated/sql-clickhouse/` set applies; the Task 8.2 flip test
`test_full_generated_set_currently_fails_nullable_array` was updated accordingly.

**Friction.** Finding #25: the SQL emitter renders an optional `array<T>` as
`Nullable(Array(T))`, which ClickHouse rejects (`ILLEGAL_TYPE_OF_ARGUMENT`,
"Array(String) cannot be inside Nullable"). The full generated graph cannot be
applied to ClickHouse at all; the showcase's Task 8.2 apply path is limited to
the six `reporting.*` files that happen to contain no arrays.

**Proposed behavior.** Render optional arrays for ClickHouse as
`Array(Nullable(T))` (or `Array(T)` with an empty-array default), keeping the
"absent ⇔ null" semantics expressible at the value level.

**Acceptance.** Applying every generated `.sql` under `generated/sql-clickhouse`
succeeds; the Task 8.2 flip test `test_full_generated_set_currently_fails_nullable_array`
becomes a plain "applies cleanly" test.

---

## FR-6 — Globally unique deterministic index names

**Status:** Implemented in v1.8.0. Verified against the 1.8.0 regeneration: index
names are now table-prefixed (`appointment_db_by_practitioner_day`,
`daily_schedule_by_practitioner_day`), so every declared index is created; the
`#24` flip assertion was updated to the new names.

**Friction.** Finding #24: distinct models/projections generate the same index
name (`by_practitioner_day` is emitted for both `appointment_db` and
`daily_schedule`). Because the DDL uses `CREATE INDEX IF NOT EXISTS`, the second
index is silently never created — the applied database lost the `by_name` index
on `patient_db`, so Task 9.2 list/search has no supporting index.

**Proposed behavior.** Namespace generated index names by their table (e.g.
`appointment_db__by_practitioner_day`), or scope the `IF NOT EXISTS` check per
`(table, index)` so identical names on different tables are both created.

**Acceptance.** Running the generated DDL twice over a fresh database creates
every declared index; `\di` shows both `by_practitioner_day` variants.

---

## FR-7 — Cwd-independent deterministic registry-id resolution

**Status:** Implemented in v1.8.0. Verified against the 1.8.0 regeneration: the
registry-id ledger is now resolved relative to the model root — it is written to
`model/registry-ids.lock` (beside the workspace) rather than a cwd-relative
`.modelable/registry-ids.lock`, and `modelable compile` is independent of the
invocation directory. Note the ids were reallocated as part of the move
(`billing.InvoiceId: 1`, `patient.PatientId: 2`), which the registry-id flip test
was updated for.

**Friction.** Registry-id assignment reads/writes `.modelable/registry-ids.lock`
relative to the **current working directory**. Compiling the same model from a
different cwd reassigns registry ids, which changes generated OpenAPI schema
names and breaks byte-determinism across machines/CI. Task 9.0 had to pin the
probe to run with `cwd = model dir` as a workaround.

**Proposed behavior.** Resolve the registry-id lock relative to the model root
(or accept an explicit `--registry-ids <path>`), so `modelable compile` is
independent of the invocation directory.

**Acceptance.** `modelable compile --target openapi` run from two different
working directories over the same model produces byte-identical output.

---

## FR-8 — Ship `openapi` in a versioned release (with a real version string)

**Status:** Implemented in v1.8.0. `modelable capabilities` includes `openapi` on
the pinned release, `modelable --version` reports `1.8.0`, and this showcase's
`tests/integration/test_openapi_checkpoint.py` now runs and passes without the
`requires_openapi` skip.

**Friction.** Task 9.0 verified that the `openapi` target (Phase A component
schemas + Phase B paths, upstream #350–#359) exists only on `origin/main`; the
pinned `1.7.0` does not list `openapi` in `modelable capabilities`. Adopting
OpenAPI (Task 9.6) therefore requires a canary git install. Independently,
`modelable --version` still prints `1.7.0` on the canary build, so the installed
revision is not discoverable from the CLI.

**Proposed behavior.** Cut a tagged release containing the `openapi` target and
make `--version` reflect the actual version/revision.

**Acceptance.** `pip index`/release install has `openapi` in capabilities; the
showcase's `tests/integration/test_openapi_checkpoint.py` `requires_openapi`
skip becomes a plain pass on the pinned release; `modelable --version` reports
a distinct value from the previous release.

---

## FR-9 — Canonical, round-trippable `time` / `duration` serialization

**Status:** Implemented in v1.8.0. Verified against the 1.8.0 regeneration:
`time` fields compile to `chrono::NaiveTime`/`chrono::DateTime<chrono::Utc>` and
`duration` fields to `chrono::Duration` in generated Rust, and the SQL target
renders them canonically, so the API can bind directly without casts or hand
parsers.

**Friction.** `time` and `duration` fields compile to opaque strings in Rust and
`INTERVAL`/`TEXT` in SQL with no single canonical wire format. Task 9.3 had to:
validate `"HH:MM:SS"` by hand, reject `end <= start`, bind durations through
`CAST($n AS interval)`, and read them back via `column::text` — and a client's
ISO-8601 duration string and the Postgres-rendered interval do not round-trip
to the same text.

**Proposed behavior.** Pick one canonical representation per scalar type (e.g.
RFC3339-ish `HH:MM:SS` for `time`, ISO-8601 for `duration`) and emit it
consistently across SQL and Rust — ideally as typed Rust values
(`NaiveTime`, `chrono::Duration`) rather than raw strings — so the API binds
directly with no casts or hand parsers.

**Acceptance.** Writing `bufferDuration` and reading the appointment back
returns the identical string; the showcase's `parse_time`/`CAST(... AS interval)`
workarounds are removed.

---

## FR-10 — Value objects as `jsonb` (or generated query operators)

**Status:** Implemented in v1.8.0. Verified against the 1.8.0 regeneration:
value-object fields now emit as `JSONB` columns
(`contact JSONB NOT NULL`, `slot JSONB NOT NULL` in
`generated/sql-postgres/patient.PatientDb.v2.sql` / `scheduling.AppointmentDb.v1.sql`),
so the API can drop its hand-written `::text::jsonb` casts.

**Friction.** Value objects (`PatientContactDetails`, `PatientAddress`,
`TimeRange`) are stored as `TEXT` JSON columns. Searches and ordering over them
require hand-written casts in the showcase: `contact::jsonb ->> 'email' ILIKE ...`
(Task 9.2 email search) and `slot::jsonb ->> 'start'` (Task 9.3 schedule
ordering). If a value object's JSON were ever malformed, those queries 500.

**Proposed behavior.** Emit `jsonb` (with an optional `GIN` index) for value
objects in the Postgres target, or generate query operators / a filter language
so common predicates over value-object fields don't require raw casts.

**Acceptance.** `GET /api/patients?email=...` and
`GET /api/schedule?date=...` are expressible without `::jsonb` casts in
application code.

---

## FR-11 — Foreign keys from `ref<>` in generated DDL

**Status:** Partially implemented in v1.8.0. FKs are now emitted for `ref<>`
fields, but new finding [#27](UPSTREAM_FINDINGS.md#27) makes them unusable: the
`REFERENCES` clause names the model (`REFERENCES patient (patient_id)`) instead
of the bound table (`patient_db`), so the full generated DDL cannot be applied.

**Friction.** Cross-model references (`appointment.patientId:
ref<patient.Patient@2>`) compile to plain `TEXT NOT NULL` with no foreign key,
so referential integrity is unenforced and the API must decide whether to
validate references itself (Tasks 9.2/9.3 accept any UUID).

**Proposed behavior.** Emit `REFERENCES` constraints for `ref<>` fields
(behind a toggle, since multi-target and bootstrap order may need it opt-in)
from the generated DDL.

**Acceptance.** The generated `appointment_db.patient_id` carries
`REFERENCES patient_db(patient_id)`; inserting an appointment for an unknown
patient fails at the database rather than silently passing.

---

## FR-12 — Official event-sink/outbox materialising event projections

**Status:** Implemented in v1.8.0. An `event-sink` compile target now ships
(`modelable capabilities` lists it; `generated/event-sink/` is produced), giving
consumers an official contract for materialising event projections.

**Friction.** The plan for Task 9.5 explicitly falls back to hand-written
SQL/API aggregation "rather than Modelable runtime materialisation": event
projections exist as SQL tables (`appointment_event`, `patient_event`) but
nothing in the toolchain writes them, and the analytics endpoint must be
implemented manually against ClickHouse.

**Proposed behavior.** Provide an official event-sink / outbox contract (or a
`modelable serve`/daemon mode) that materialises `event` projections — including
ClickHouse `reporting.*` tables — as mutations occur, so the analytics and
reporting views are maintained by the generator/runtime rather than application
code.

**Acceptance.** After a booking mutation, `appointment_event` (and the
ClickHouse `daily_schedule`/`monthly_clinic_stats` sources) reflect the change
without bespoke insert code in the API.

---

## FR-13 — A generated registry/contract module

**Status:** Implemented in v1.8.0. Verified against the 1.8.0 regeneration: the
`registry` target produces `generated/registry/registry.json` enumerating each
compiled model's registry id, schema version, and content signature, so the
`/health` contract object can be built from generated data instead of
hand-assembled constants.

**Friction.** Task 9.1 built the `/health` contract linkage by hand-picking one
model (`PatientPatientV2::SCHEMA_VERSION`, `PatientId::REGISTRY_ID`, content
signature) out of the generated crate. The constants exist on generated types,
but there is no single generated artifact that enumerates every compiled model.

**Proposed behavior.** Generate a `registry` module (or `modelable compile
--target manifest`) that lists each compiled model's registry id, schema
version, and content signature, so contract/health endpoints and drift checks
can be generated rather than hand-assembled.

**Acceptance.** The showcase `/health` contract object is built from the
generated registry for all compiled models, not hand-wired for `patient` only.

---

## FR-14 — Resolve `ref<>` fields to a real component in generated OpenAPI

**Status:** Open. New finding [#35](UPSTREAM_FINDINGS.md#35): the `openapi`
target emits a `$ref` to the bare source entity for `ref<Domain.Entity@N>`
fields (e.g. `"$ref": "#/components/schemas/patient.Patient.v2"`), but no
component schema for a bare entity is ever emitted - only its projections
(`Db`/`Request`/`Reply`/`Event`) are. Every `ref<>` field in this showcase's
model (`Appointment.patientId`, `Encounter.appointmentId`,
`Observation.encounterId`, `Invoice.encounterId`) produces an unresolvable
reference, so no `ref<>`-bearing projection's OpenAPI schema passes standard
validation (`openapi-spec-validator` raises `PointerToNowhere`). This is the
OpenAPI analogue of FR-11's SQL DDL foreign-key friction.

**Friction.** A consumer generating an OpenAPI-derived client/mock/docs page
for any endpoint whose request or reply carries a `ref<>` field gets a broken
component graph, with no local workaround other than skipping full-document
resolution.

**Proposed behavior.** Resolve a `ref<Domain.Entity@N>` field's OpenAPI schema
to the referenced entity's `@key` field type (its identifier semantic type,
e.g. `PatientId`) - what the field actually carries on the wire - rather than
a `$ref` to the entity itself. This mirrors how other targets already treat
`ref<>`: `sql-postgres` emits a `FOREIGN KEY` to the key column, not the model.

**Acceptance.** `openapi-spec-validator` validates
`generated/openapi/openapi.json` for a model containing a `ref<>` field with
no `PointerToNowhere` errors, and the resolved schema for the `ref<>` field
matches the referenced entity's `@key` type.