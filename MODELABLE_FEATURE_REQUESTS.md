# Modelable Feature Requests — Showcase-Driven Improvements

This document collects feature requests for the **Modelable** generator (upstream,
`https://github.com/ktjn/modelable`) derived from building the Modelable Showcase
(acceptance product in this repository, pinned to `modelable==1.7.0`).

Each request names the concrete friction the showcase hit, maps it to the
relevant task and/or `UPSTREAM_FINDINGS.md` entry, proposes a behavior, and gives
an acceptance hint. The requests are ordered roughly by impact on this project.

This log is maintained in lockstep with `UPSTREAM_FINDINGS.md` per
`UPSTREAM_POLICY.md` §13: new findings that imply a capability update this
document, and a finding that is fixed upstream updates the status of the FRs
that cite it in the same commit.

Status is informational for the upstream team; nothing here is fixed in the
pinned 1.7.0 release.

| ID | Feature | Friction source | Status |
|----|---------|-----------------|--------|
| FR-1 | Emit `PRIMARY KEY`/`UNIQUE` from `@key` in generated DDL | Tasks 9.2/9.3 duplicate handling | Proposed |
| FR-2 | Server-generated key fields (IDs dropped from the request projection) | Tasks 9.2/9.3 | Proposed |
| FR-3 | Symmetric Rust serde attributes (`#[serde(default)]`) | Tasks 9.2/9.3 reply round-trip | Proposed |
| FR-4 | Generated Rust compiles for every supported model | Finding #14 (clinical/billing) | Proposed |
| FR-5 | Legal ClickHouse rendering for optional arrays | Finding #25 | Proposed |
| FR-6 | Globally unique deterministic index names | Finding #24 | Proposed |
| FR-7 | Cwd-independent deterministic registry-id resolution | Task 9.0 OpenAPI probe | Proposed |
| FR-8 | Ship `openapi` in a versioned release (with a real version string) | Task 9.0 | Proposed |
| FR-9 | Canonical, round-trippable `time`/`duration` serialization | Task 9.3 | Proposed |
| FR-10 | Value objects as `jsonb` (or generated query operators) | Tasks 9.2/9.3 search/ordering | Proposed |
| FR-11 | Foreign keys from `ref<>` in generated DDL | Tasks 9.2/9.3 | Proposed |
| FR-12 | Official event-sink/outbox materialising event projections | Task 9.5 plan | Proposed |
| FR-13 | A generated registry/contract module | Task 9.1 `/health` | Proposed |

---

## FR-1 — Emit `PRIMARY KEY` / `UNIQUE` from `@key` in generated DDL

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