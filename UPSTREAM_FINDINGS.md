# Modelable Upstream Findings Log

**Status:** living document — append an entry every time this showcase discovers real Modelable behavior that diverges from its own documentation, crashes instead of producing a diagnostic, or fails to implement something its own source code visibly intends to (reserved-but-unused diagnostic codes, dead IR variants, etc.).

**Purpose:** `UPSTREAM_POLICY.md` §1 requires that a gap discovered here get "exposed rather than hidden." A finding scattered across a commit message or a PR description satisfies the letter of that a single time, but is invisible to the next person unless they read the entire git history. This file is the one place all of them are supposed to be visible at once.

**Not this file's job:** process (`UPSTREAM_POLICY.md` owns *how* to handle a gap), requirements (`SPEC.md` owns *what* the showcase must do), or task sequencing (`IMPLEMENTATION_PLAN.md` owns *when*). This file only records *what was actually observed*, against *which exact version*, with a *minimal reproduction*. When SPEC.md needs to state a consequence of a finding here (e.g. "this negative fixture doesn't exist because the behavior it would test doesn't exist"), it should say so briefly and point back here for the detail, not restate the detail.

**Every entry needs:** a reproduction a stranger can run against the pinned release without any of this repo's other context, the exact observed output, what was expected instead, which `UPSTREAM_POLICY.md` §6 case it falls under, and the workaround (if any) this showcase used, with a pointer to where.

**Verified against:** `modelable==1.7.0` (the pinned release, see `.modelable-version`) unless noted otherwise. Several entries were re-checked against upstream `main` at commit `e2fe6ac54e6cba42982c5bbeeacad95524393762` specifically because the finding looked like it might already be fixed there — the log says explicitly whenever that check happened, and doesn't claim it otherwise.

## Status summary

| # | Finding | Category | Case | Status |
|---|---|---|---|---|
| 1 | [`@wire(json: {...})` crashes instead of diagnosing an unsupported key](#1-wirejson--crashes-instead-of-diagnosing-an-unsupported-key) | Crash | A | Fixed in v1.8.0 (via [ktjn/modelable#354](https://github.com/ktjn/modelable/pull/354)) |
| 2 | [`ref<Model@N#hash>` cannot pin most real SHA-256 signatures](#2-refmodelnhash-cannot-pin-most-real-sha-256-signatures) | Grammar gap | A | Fixed in v1.8.0 (via #354) |
| 3 | [`group by` cannot take a function-call expression](#3-group-by-cannot-take-a-function-call-expression) | Grammar gap | A | Fixed in v1.8.0 (via #354) |
| 4 | [`where` followed by `pick`/`omit` on the next line fails to parse](#4-where-followed-by-pickomit-on-the-next-line-fails-to-parse) | Grammar gap | A | Fixed in v1.8.0 (via #354) |
| 5 | [Unresolvable/ambiguous bare semantic-type field references silently degrade instead of erroring](#5-unresolvableambiguous-bare-semantic-type-field-references-silently-degrade-instead-of-erroring) | Missing diagnostic | A | Fixed in v1.8.0 (via #354) |
| 6 | [`compile --target protobuf` crashes on reservation reuse instead of diagnosing it](#6-compile---target-protobuf-crashes-on-reservation-reuse-instead-of-diagnosing-it) | Crash | A | Fixed in v1.8.0 (via #354) |
| 7 | [CEL type-mismatch checking is not implemented](#7-cel-type-mismatch-checking-is-not-implemented) | Missing feature | A | Fixed in v1.8.0 (via #354) |
| 8 | [`ref<Model @ >=N <M>>` version-range notation is easy to double-bracket](#8-refmodel--n-m-version-range-notation-is-easy-to-double-bracket) | Docs clarity | C | N/A — no code fix needed |
| 9 | [A second `auto projections` declaration for another version of the same model is silently dropped](#9-a-second-auto-projections-declaration-for-another-version-of-the-same-model-is-silently-dropped) | Silent data loss | A | Fixed in v1.8.0 (via #354) |
| 10 | [`modelable diff` never reports governance (access/classification/@pii) changes for entities and aggregates, only for projections](#10-modelable-diff-never-reports-governance-accessclassificationpii-changes-for-entities-and-aggregates-only-for-projections) | Missing diagnostic | A | Fixed in v1.8.0 (via #354) |
| 11 | [`reserved protobuf { names: [...] }` must use the generated snake_case Protobuf name, not the Modelable source field name, for cross-version reuse checks](#11-reserved-protobuf-names--must-use-the-generated-snake_case-protobuf-name-not-the-modelable-source-field-name-for-cross-version-reuse-checks) | Inconsistent behavior | A | Fixed in v1.8.0 (via #354) |
| 12 | [`compile --target typescript` never imports a field's semantic type - every semantic-typed field is a compile error](#12-compile---target-typescript-never-imports-a-fields-semantic-type---every-semantic-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Fixed in v1.8.0 (via #354) |
| 13 | [`compile --target typescript` never emits any imports at all for auto-generated projections (Db/Request/Reply/Event)](#13-compile---target-typescript-never-emits-any-imports-at-all-for-auto-generated-projections-dbrequestreplyevent) | Crash (broken generated code) | A | Fixed in v1.8.0 (via #354) |
| 14 | [`compile --target rust` loses named-type resolution for optional array fields specifically](#14-compile---target-rust-loses-named-type-resolution-for-optional-array-fields-specifically) | Crash (broken generated code) | A | Fixed in v1.8.0 (via [ktjn/modelable#355](https://github.com/ktjn/modelable/pull/355)) |
| 15 | [`compile --target csharp` never resolves named-type references to the emitted stable type name - every value-type-typed field is a compile error](#15-compile---target-csharp-never-resolves-named-type-references-to-the-emitted-stable-type-name---every-value-type-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Fixed in v1.8.0 (#365) for same-namespace refs; cross-namespace refs still unresolved — see [## 28](#28-compile---target-csharp-never-imports-or-qualifies-types-from-another-domain---cross-domain-field-references-are-still-compile-errors) |
| 16 | [`compile --target csharp` never emits semantic types at all - every semantic-typed field is a compile error](#16-compile---target-csharp-never-emits-semantic-types-at-all---every-semantic-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Fixed in v1.8.0 (#365) — residual cross-namespace refs tracked in [## 28](#28-compile---target-csharp-never-imports-or-qualifies-types-from-another-domain---cross-domain-field-references-are-still-compile-errors) |
| 17 | [`compile --target java` never resolves named-type references to the emitted stable type name - every value-type-typed field is a compile error](#17-compile---target-java-never-resolves-named-type-references-to-the-emitted-stable-type-name---every-value-type-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Fixed in v1.8.0 (#365) for same-package refs; cross-package refs still unresolved — see [## 29](#29-compile---target-java-never-imports-or-qualifies-types-from-another-domain---cross-domain-field-references-are-still-compile-errors) |
| 18 | [`compile --target java` never emits semantic types at all - every semantic-typed field is a compile error](#18-compile---target-java-never-emits-semantic-types-at-all---every-semantic-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Fixed in v1.8.0 (#365) — residual cross-package refs tracked in [## 29](#29-compile---target-java-never-imports-or-qualifies-types-from-another-domain---cross-domain-field-references-are-still-compile-errors) |
| 19 | [`compile --target python` never resolves named-type references to the emitted stable type name - every value-type-typed annotation is a NameError](#19-compile---target-python-never-resolves-named-type-references-to-the-emitted-stable-type-name---every-value-type-typed-annotation-is-a-nameerror) | Crash (broken generated code) | A | Naming mismatch fixed in v1.8.0 (#365); still unresolved overall (missing import) — see [## 30](#30-compile---target-python-never-imports-referenced-types-from-other-modules---annotations-still-do-not-resolve-cross-module) |
| 20 | [`compile --target python` never emits semantic types at all - every semantic-typed annotation is a NameError](#20-compile---target-python-never-emits-semantic-types-at-all---every-semantic-typed-annotation-is-a-nameerror) | Crash (broken generated code) | A | Fixed in v1.8.0 (#365) — residual cross-module refs tracked in [## 30](#30-compile---target-python-never-imports-referenced-types-from-other-modules---annotations-still-do-not-resolve-cross-module) |
| 21 | [`compile --target go` never resolves named-type references to the emitted stable type name - every value-type-typed field is a compile error](#21-compile---target-go-never-resolves-named-type-references-to-the-emitted-stable-type-name---every-value-type-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Fixed in v1.8.0 (#365) for same-package refs; cross-package refs still unresolved — see [## 31](#31-compile---target-go-never-imports-or-qualifies-types-from-another-package---cross-domain-field-references-are-still-compile-errors) |
| 22 | [`compile --target go` never emits semantic types at all - every semantic-typed field is a compile error](#22-compile---target-go-never-emits-semantic-types-at-all---every-semantic-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Fixed in v1.8.0 (#365) — residual cross-package refs tracked in [## 31](#31-compile---target-go-never-imports-or-qualifies-types-from-another-package---cross-domain-field-references-are-still-compile-errors) |
| 23 | [`compile --target grpc` emits one standalone service file per model into the same `modelable.<domain>.<version>.scalable` package - the full emitted graph cannot be compiled together](#23-compile---target-grpc-emits-one-standalone-service-file-per-model-into-the-same-modelabledomainversionscalable-package---the-full-emitted-graph-cannot-be-compiled-together) | Crash (broken generated code) | A | Fixed in v1.8.0 (via #365) |
| 24 | [`compile --target sql-postgres` emits bare secondary-index names that collide across tables in the shared schema - the full graph cannot be applied as-is](#24-compile---target-sql-postgres-emits-bare-secondary-index-names-that-collide-across-tables-in-the-shared-schema---the-full-graph-cannot-be-applied-as-is) | Silent data loss | A | Fixed in v1.8.0 (via #365) — index names now table-prefixed |
| 25 | [`compile --target sql-clickhouse` emits optional array fields as `Nullable(Array(T))` - an illegal ClickHouse type, so the full generated graph cannot be applied at all](#25-compile---target-sql-clickhouse-emits-optional-array-fields-as-nullablearrayt---an-illegal-clickhouse-type-so-the-full-generated-graph-cannot-be-applied-at-all) | Crash (broken generated code) | A | Fixed in v1.8.0 (via #365) — optional arrays no longer wrapped in `Nullable` |
| 26 | [`compile --target rust` emits `status: src.status.into()` between projection status enums without generating the `From` impl - billing-core still does not compile](#26-compile---target-rust-emits-status-srcstatusinto-between-projection-status-enums-without-generating-the-from-impl---billing-core-still-does-not-compile) | Crash (broken generated code) | A | Fixed in v1.9.0; usable from v1.9.2 (after #35/#36) |
| 27 | [`compile --target sql-postgres` emits `FOREIGN KEY (...)` referencing the model name, not the bound table name - the full graph cannot be applied](#27-compile---target-sql-postgres-emits-foreign-key--referencing-the-model-name-not-the-bound-table-name---the-full-graph-cannot-be-applied) | Crash (broken generated code) | A | Fixed in v1.9.4 |
| 28 | [`compile --target csharp` never imports or qualifies types from another domain - cross-domain field references are still compile errors](#28-compile---target-csharp-never-imports-or-qualifies-types-from-another-domain---cross-domain-field-references-are-still-compile-errors) | Crash (broken generated code) | A | Fixed in v1.9.3 (via [ktjn/modelable#391](https://github.com/ktjn/modelable/pull/391)) |
| 29 | [`compile --target java` never imports or qualifies types from another domain - cross-domain field references are still compile errors](#29-compile---target-java-never-imports-or-qualifies-types-from-another-domain---cross-domain-field-references-are-still-compile-errors) | Crash (broken generated code) | A | Fixed in v1.9.3 (via [ktjn/modelable#391](https://github.com/ktjn/modelable/pull/391)) |
| 30 | [`compile --target python` never imports referenced types from other modules - annotations still do not resolve cross-module](#30-compile---target-python-never-imports-referenced-types-from-other-modules---annotations-still-do-not-resolve-cross-module) | Crash (broken generated code) | A | Fix verified in [PR #418](https://github.com/ktjn/modelable/pull/418) (draft) |
| 31 | [`compile --target go` never imports or qualifies types from another package - cross-domain field references are still compile errors](#31-compile---target-go-never-imports-or-qualifies-types-from-another-package---cross-domain-field-references-are-still-compile-errors) | Crash (broken generated code) | A | Fixed in v1.9.3 (via [ktjn/modelable#391](https://github.com/ktjn/modelable/pull/391)) |
| 32 | [`modelable generate --from json-schema` emits the raw `$ref` JSON Pointer (`#/$defs/<Type>`) as a field type - imported schemas fail to parse](#32-modelable-generate---from-json-schema-emits-the-raw-ref-json-pointer-defstype-as-a-field-type---imported-schemas-fail-to-parse) | Crash (broken generated code) | A | Fixed in v1.9.2 (verified on 1.9.3) |
| 33 | [`modelable generate --from odcs` imports semantic/value-type references without their declarations - imported models fail validation](#33-modelable-generate---from-odcs-imports-semanticvalue-type-references-without-their-declarations---imported-models-fail-validation) | Crash (broken generated code) | A | Fixed in v1.9.2 (verified on 1.9.3) |
| 34 | [`compile --target rust` marks every `Option` field `#[serde(skip_serializing_if = "Option::is_none")]` without `#[serde(default)]` - a serialized projection cannot be deserialized back when an optional is `None`](#34-compile---target-rust-marks-every-option-field-serde-skip_serializing_if--optionis_none-without-serde-default---a-serialized-projection-cannot-be-deserialized-back-when-an-optional-is-none) | Crash (broken generated code) | A | Fixed in v1.9.0; usable from v1.9.1 |
| 35 | [`compile --target rust` emits `#[serde(default)]` twice on every optional field that already carried it - a hard serde derive error, so all generated Rust crates fail to compile](#35-compile---target-rust-emits-serde-default-twice-on-every-optional-field-that-already-carried-it---a-hard-serde-derive-error-so-all-generated-rust-crates-fail-to-compile) | Crash (broken generated code) | A | Fixed in v1.9.1 (via [ktjn/modelable#387](https://github.com/ktjn/modelable/pull/387)) |
| 36 | [`compile --target rust` emits cross-domain status-enum `From` impls importing via `super::{domain}::` - invalid for sibling top-level modules in the same package crate, so billing-core fails to compile](#36-compile---target-rust-emits-cross-domain-status-enum-from-impls-importing-via-superdomain---invalid-for-sibling-top-level-modules-in-the-same-package-crate-so-billing-core-fails-to-compile) | Crash (broken generated code) | A | Fixed in v1.9.2 (via [ktjn/modelable#389](https://github.com/ktjn/modelable/pull/389)) |
| 37 | [`compile --target go/java/python/csharp` 1.9.x cross-domain import feature over-imports all cross-domain types into every file and emits wrong/unresolvable import paths, and cross-domain semantic refs still emit a bogus `pascalized` named type - standalone packages and full-set builds break](#37-compile---target-gojavapythoncsharp-19x-cross-domain-import-feature-over-imports-all-cross-domain-types-into-every-file-and-emits-wrongunresolvable-import-paths-and-cross-domain-semantic-refs-still-emit-a-bogus-pascalized-named-type---standalone-packages-and-full-set-builds-break) | Crash (broken generated code) | A | Fixed in v1.9.3 (via [ktjn/modelable#391](https://github.com/ktjn/modelable/pull/391)) |
| 38 | [`compile --target openapi` emits a `$ref` to the bare source entity for `ref<Domain.Entity@N>` fields, but no component schema exists for a bare entity - the reference is unresolvable](#38-compile---target-openapi-emits-a-ref-to-the-bare-source-entity-for-refdomainentityn-fields-but-no-component-schema-exists-for-a-bare-entity---the-reference-is-unresolvable) | Invalid generated output | A | Fixed in v1.9.4 |
| 39 | [`compile --target openapi` emits Modelable-source camelCase property names while `compile --target rust` emits the language-idiomatic snake_case field names as-is on the wire - the two targets disagree about the same model's JSON contract](#39-compile---target-openapi-emits-modelable-source-camelcase-property-names-while-compile---target-rust-emits-the-language-idiomatic-snake_case-field-names-as-is-on-the-wire---the-two-targets-disagree-about-the-same-models-json-contract) | Inconsistent behavior | A | Fixed in v1.9.4 |
| 40 | [`compile --target typescript` never marks an optional field `?:` - every field is emitted as required, even `@server` fields and explicit `?` fields](#40-compile---target-typescript-never-marks-an-optional-field--every-field-is-emitted-as-required-even-server-fields-and-explicit--fields) | Missing feature (broken generated code) | A | Fixed in v1.9.4 |
| 41 | [`compile --target sql-clickhouse` emits a `bloom_filter` secondary index on a composite index that includes a `DateTime64` column - `CREATE TABLE` succeeds but every `INSERT` into the table fails](#41-compile---target-sql-clickhouse-emits-a-bloom_filter-secondary-index-on-a-composite-index-that-includes-a-datetime64-column---create-table-succeeds-but-every-insert-into-the-table-fails) | Invalid generated output | A | Fix verified in [PR #417](https://github.com/ktjn/modelable/pull/417) (draft) |
| 42 | [`modelable capabilities --format json` reports `annotation:custom` as `"status": "implemented"`, but the grammar has no production that reaches it - `@custom(...)` is a hard parse error on every attempt](#42-modelable-capabilities---format-json-reports-annotationcustom-as-status-implemented-but-the-grammar-has-no-production-that-reaches-it---custom-is-a-hard-parse-error-on-every-attempt) | Inconsistent behavior | A | Fix verified in [PR #417](https://github.com/ktjn/modelable/pull/417) (draft) |
| 43 | [`compile --target fhir-profile` emits extension sidecar `StructureDefinition`s that fail the official HL7 FHIR Validator, and references two annotation-marker extension URLs for which no `StructureDefinition` is ever emitted at all](#43-compile---target-fhir-profile-emits-extension-sidecar-structuredefinitions-that-fail-the-official-hl7-fhir-validator-and-references-two-annotation-marker-extension-urls-piiclassification-for-which-no-structuredefinition-is-ever-emitted-at-all) | Invalid generated output | A | Partially fixed in [PR #417](https://github.com/ktjn/modelable/pull/417) (draft) — see [## 45](#45-compile---target-fhir-profile-emits-extensionurl-elements-with-no-explicit-type-so-snapshot-generation-still-fails-the-official-hl7-fhir-validator-even-after-417) |
| 44 | [`compile --target avro` crashes on any field with a default value - `TypeError: cannot use 'dict' as a set element`](#44-compile---target-avro-crashes-on-any-field-with-a-default-value---typeerror-cannot-use-dict-as-a-set-element) | Crash | A | Fix verified in [PR #417](https://github.com/ktjn/modelable/pull/417) (draft); found on upstream `main`, not present on pinned `1.9.4` |
| 45 | [`compile --target fhir-profile` emits `Extension.url` elements with no explicit type, so snapshot generation still fails the official HL7 FHIR Validator even after #417](#45-compile---target-fhir-profile-emits-extensionurl-elements-with-no-explicit-type-so-snapshot-generation-still-fails-the-official-hl7-fhir-validator-even-after-417) | Invalid generated output | A | Still open after two PR #418 revisions — see [## 45](#45-compile---target-fhir-profile-emits-extensionurl-elements-with-no-explicit-type-so-snapshot-generation-still-fails-the-official-hl7-fhir-validator-even-after-417) |

"Case" refers to `UPSTREAM_POLICY.md` §6's decision tree. All findings below are Case A ("Modelable is wrong or incomplete") except #8, which is Case C (an intentional-looking design whose documentation example is easy to misread) — kept here anyway because misreading it produces a real parse error, which is exactly the kind of thing this log exists to save the next person from re-discovering.

**#1–#13** were all fixed in [ktjn/modelable#354](https://github.com/ktjn/modelable/pull/354) (merge commit `9ccb2b9` on `origin/main`), shipped in **v1.8.0**. This showcase moved its pin from `1.7.0` to **`1.8.0`** (`.modelable-version`, `scripts/install-modelable.sh`), reinstalled, and regenerated all 20 targets; each finding's exact reproduction was re-run against the 1.8.0 output and the fix verified (the per-entry notes below record what changed per finding). Concretely for #12/#13: the typescript emitter now emits imports correctly, so `apps/web/src/generated-types.ts`'s hand-written workaround is no longer necessary against the pinned release and was removed.

**#14** was fixed in [ktjn/modelable#355](https://github.com/ktjn/modelable/pull/355) (merge commit `b474232`), also shipped in **v1.8.0**. Re-verified against the 1.8.0 output: `generated/rust/clinical-core` now compiles (`cargo check` clean), and `patient.PatientContactDetailsV0` is resolved in `clinical.ClinicalDiagnosisV0.v1` (the generated `clinical-diagnosis-v0.rs` references the imported value type directly instead of failing the optional-array resolution). Note this showcase's Rust probe no longer asserts the pre-fix failure.

**#15–#22** (the C#/Java/Python/Go named-type and semantic-type pairs) were all addressed in [ktjn/modelable#365](https://github.com/ktjn/modelable/pull/365) ("address showcase emitter findings"), shipped in **v1.8.0** — but only **partially**. What was fixed: within a single domain, the emitters now resolve named-type references to the emitted stable type names and emit semantic types (C# `PatientPatientId`/`SchedulingPractitionerId`, Java/Python/Go analogues, etc.), so single-domain compile/probe checks that previously failed now pass. What remains broken: **references across domains/namespaces/packages/modules still do not resolve** — the emitters never emit imports or qualified names for types declared in another domain, so the *full generated graph* for csharp/java/python/go still does not compile (verified on the 1.8.0 output; failures are now `CS0246`/`cannot find symbol`/`NameError`/`undefined` on cross-domain names like `PatientContactDetailsV0`, `SchedulingPractitionerId`, `SchedulingTimeRangeV0`, `PatientPatientId`). Those residuals are logged as new findings **#28–#31** below; the `#15–#22` entries' workaround sections are updated to point at them. Also fixed by #365: **#23** (grpc now emits one service file per domain, so `protoc` over the whole `generated/grpc/` output succeeds), **#24** (sql-postgres secondary-index names are now table-prefixed — `patient_db_by_status`, `appointment_db_by_name` — so the full DDL graph applies with every declared index present, and the `#24` flip assertions were updated to the new names), and **#25** (sql-clickhouse no longer emits `Nullable(Array(T))` for optional array fields — `alternate_phone_numbers Array(String)` etc. apply cleanly, so the full clickhouse set now applies and the `#25` flip assertion was updated accordingly).

**#26–#33** are new findings discovered while reviewing the v1.8.0 output (each empirically verified against the 1.8.0 regeneration; full reproductions in the entries below). **#26** was fixed upstream (shipped v1.9.0); the pin bump that adopted it surfaced **#34** (fixed v1.9.0), **#35** (fixed v1.9.1 via #387), and **#36** (fixed v1.9.2 via #389). **#32**/**#33** were fixed in v1.9.2. **#28–#31** were fixed by the **#37** cross-domain emitter fix (shipped v1.9.3 via #391). Findings **#27** and **#38–#40** are fixed in **v1.9.4** and the showcase flip tests now assert the repaired behavior.

**#34** was discovered while redoing the generated Rust API layer (`apps/api`, Task 9.1–9.3) against the 1.8.0 output: the rust emitter marks every `Option` field `#[serde(skip_serializing_if = "Option::is_none")]` but never adds `#[serde(default)]`, so a *serialized* projection cannot be *deserialized* back into the same type whenever any optional field is `None` (serde demands the key unless `default` is present). The showcase API's own create/fetch round-trips therefore cannot round-trip a reply with a `None` optional through the generated type, and `apps/api/tests/scheduling_api.rs::appointment_reply_json_shape_matches_generated_types` pins that reality (it asserts the created reply's fields, and deserializes a hand-built full JSON with all optionals present rather than the API's own omitted-optional output). #34 was fixed upstream in **v1.9.0**, but that fix introduced **#35** (below).

**#35** was discovered while re-pinning to 1.9.0 to adopt the #26 fix: 1.9.0's #34 fix writes `#[serde(default)]` a second time on every `Option` field that already carried one (the value-type projection files), a hard serde derive error that breaks all three generated Rust crates. Fixed upstream in **v1.9.1** via #387. **#36** was then discovered re-pinning to 1.9.1: the same emitter line's #26 fix emitted cross-domain status-enum `From` imports via `super::{domain}::`, invalid for sibling top-level modules in a package crate — fixed upstream in **v1.9.2** via #389. With the showcase pinned to **1.9.2**, all three generated Rust crates compile and Task 9.4's generated clinical/billing contracts are buildable.

---

## 1. `@wire(json: {...})` crashes instead of diagnosing an unsupported key

**Status:** Fixed in v1.8.0 via [ktjn/modelable#354](https://github.com/ktjn/modelable/pull/354) (shipped in the 1.8.0 release; verified against this showcase's 1.8.0 regeneration — the exact reproduction below now produces a clean diagnostic, not a traceback).

**Discovered:** Task 2.1 (patient domain), PR #3.

**Reproduction:**

```mdl
domain probe {
  owner: "test"
  value Thing {
    @wire(json: {name: "x"})
    notes?: string
  }
}
```

```bash
modelable validate .
```

This is not an invented edge case — it is copied nearly verbatim from `docs/language-reference.md`'s own annotation reference table, which shows `@wire(avro: "logicalType", json: { name: "x" })` as the canonical example of the `@wire(key: value, ...)` syntax.

**Observed:**

```text
Traceback (most recent call last):
  ...
  File ".../modelable/validation/semantic.py", line 624, in _validate_json_wire_hint
    if hint.encoding not in _VALID_JSON_ENCODINGS:
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: cannot use 'dict' as a set element (unhashable type: 'dict')
```

An unhandled Python exception and a raw traceback, not a CLI diagnostic.

**Root cause (read from source, not guessed):** the `json` wire target only recognizes specific map keys (`encoding`, `case`, `overrides`; `fieldCase` is model/projection-level only — see `validation/semantic.py::_validate_json_wire_hint`). `avro` is not in `_VALID_WIRE_TARGETS = {"json", "rust", "clickhouse"}` at all, and `json`'s map form doesn't accept an arbitrary `name` key. The transformer assigns the unrecognized key's value into `hint.encoding` without validating the key first, so `hint.encoding` ends up holding a raw `dict` instead of `None` or a string, and the subsequent `in _VALID_JSON_ENCODINGS` (a `set`) membership check crashes on the unhashable dict.

**Expected:** a clean `SEM` diagnostic (e.g. "unsupported json wire modifier 'name'"), matching how every other wire-hint misuse in the same function is handled.

**Showcase workaround:** `model/patient.mdl`'s `clinicalNotes` field uses `@wire(clickhouse: "string")` instead — confirmed safe against real passing upstream test fixtures (`cli/tests/test_emit_rust.py`) before using it.

---

## 2. `ref<Model@N#hash>` cannot pin most real SHA-256 signatures

**Status:** Fixed in v1.8.0 via #354 (verified against the 1.8.0 regeneration).

**Discovered:** Task 3.1 (positive edge fixtures), PR #7.

**Reproduction:**

```mdl
domain probe {
  owner: "test"
  entity Thing @ 1 (additive) {
    @key thingId: uuid
  }
  value Holder {
    pinned: ref<probe.Thing @ 1#1d7ed8fe66374d6e939d27bc37040ba405e44d3c5fb21ac5e146fd8e45babaa2>
  }
}
```

(The hash above is a real, correctly-computed `SCHEMA_CONTENT_SIGNATURE` for a `Thing@1` declaration extracted from real `compile --target rust` output — not a fabricated string.)

```bash
modelable validate .
```

**Observed:**

```text
ERROR PARSE: ...: No terminal matches '1' in the current parser context
 pinned: ref<probe.Thing @ 1#1d7ed8fe66374d6e939d27bc37040ba405e44d3c5fb21ac5e146fd8e45babaa2>
                              ^
Expected one of:
        * IDENT
```

The identical construct with a hash that happens to start with a letter (`f...`, `c...`, etc.) parses and resolves correctly — the pin mechanism itself works; only the lexing of the hash text is affected.

**Root cause:** grammar production `version_pinned: INT "#" IDENT`, and `IDENT: /[A-Za-z_][A-Za-z0-9_-]*/` — the token cannot start with a digit. A real SHA-256 hex digest is uniformly random over `[0-9a-f]`, so roughly 10/16 (62.5%) of correctly-computed signatures are rejected by the grammar purely because of their first character, independent of correctness.

**Expected:** either a dedicated hex-string token for the pin suffix (not reusing `IDENT`), or `docs/language-reference.md`'s pinned-reference example should call out the constraint explicitly so it isn't discovered by trial and error.

**Showcase workaround:** `tests/conformance/valid/version-ranges.mdl` searches real compiled output for a signature that happens to start with a letter rather than fighting the grammar — see that file's header comment for the extraction method.

---

## 3. `group by` cannot take a function-call expression

**Status:** Fixed in v1.8.0 via #354 (verified against the 1.8.0 regeneration).

**Discovered:** Task 2.4 (billing/audit/reporting domains), PR #6.

**Reproduction:**

```mdl
domain probe {
  owner: "test"
  entity Thing @ 1 (additive) {
    @key thingId: uuid
    amount: decimal(10,2)
    createdAt: timestamp
  }
  projection MonthlyThings @ 1
    from probe.Thing @ 1 as t
    group by truncate(t.createdAt, "month")
  {
    month = truncate(t.createdAt, "month")
    total = sum(t.amount)
  }
}
```

```bash
modelable validate .
```

**Observed:**

```text
ERROR CEL: <workspace>: probe.MonthlyThings@1 group by: CEL001: parse error: expected RPAREN but got 'EOF' ('')
ERROR CEL: <workspace>: probe.MonthlyThings@1 group by: CEL001: parse error: unexpected token ')'
```

**Root cause:** grammar production `group_item: /[^,\n\r{}]+/` — a raw regex that stops at the *first* comma, with no awareness of parenthesis nesting. `truncate(t.createdAt, "month")` contains a comma inside the call's argument list, so the regex splits the function call in half before the CEL layer ever sees it as one expression.

**Expected:** `group_item` should either require balanced parens before splitting on commas, or the grammar should require explicit alias-prefixed field references only in `group by` (rejecting function calls at parse time with a clear message, rather than a confusing downstream `CEL001`).

**Showcase workaround:** `model/billing.mdl`'s `Invoice@2.billingPeriod` field stores a precomputed `"YYYY-MM"` string (set at issue time) instead of deriving the month via `truncate(...)` in `group by`; `reporting.MonthlyClinicStats` groups by that plain field. See the comment on `billingPeriod` in `billing.mdl` for the full reasoning — arguably a more realistic pattern for cheap monthly rollups regardless of this limitation.

---

## 4. `where` followed by `pick`/`omit` on the next line fails to parse

**Status:** Fixed in v1.8.0 via #354 (verified against the 1.8.0 regeneration).

**Discovered:** Task 2.4 (billing/audit/reporting domains), PR #6.

**Reproduction:**

```mdl
domain probe {
  owner: "test"
  entity Thing @ 1 (additive) {
    @key thingId: uuid
    status: enum(open, closed)
    secret: string
  }
  projection OpenThings @ 1
    from probe.Thing @ 1 as t
    where t.status == "open"
    omit(t.secret)
  {
  }
}
```

```bash
modelable validate .
```

**Observed:**

```text
ERROR CEL: <workspace>: probe.OpenThings@1 where: CEL001: parse error: unexpected token 'omit'
```

**Root cause:** `where_clause` uses `FIELD_EXPRESSION`, whose lexer regex implements multi-line continuation via a negative lookahead for specific "this line starts a new clause" keywords: `@`, an identifier followed by `<-`/`=`, `generate {`, `materialisation {`, `subscription {`, `access {`, `from `, `group by`, `{`, `}`. `pick` and `omit` are not in that list, so when a selection clause immediately follows `where` on the next line, the where-predicate's raw-text capture greedily continues onto the `omit(...)` line and folds it into the same (now malformed) CEL expression.

**Expected:** `pick`/`omit` added to `FIELD_EXPRESSION`'s stop-keyword lookahead, matching how `group by` is already handled.

**Showcase workaround:** `reporting.OutstandingInvoices` (in `model/reporting.mdl`) drops the `where` filter and computes the equivalent boolean (`isOutstanding = i.status == "issued" || i.status == "overdue"`) as a plain body field instead, keeping the `omit(...)` selection. `where` stays exercised elsewhere (`reporting.DailySchedule`). No real fixture anywhere in the upstream `ktjn/modelable` repository combines `where` with `pick`/`omit` either, consistent with this being a genuinely un-exercised path rather than something already known and worked around upstream.

---

## 5. Unresolvable/ambiguous bare semantic-type field references silently degrade instead of erroring

**Status:** Fixed in v1.8.0 via #354 (verified against the 1.8.0 regeneration).

**Discovered:** Task 3.2 (negative fixtures), PR #8.

**Reproduction (unresolvable):**

```mdl
domain probe {
  owner: "test"
  entity Thing @ 1 (additive) {
    @key thingId: uuid
    category: NoSuchType
  }
}
```

```bash
modelable validate .   # exits 0, "is valid" - no NoSuchType declaration exists anywhere
modelable compile . --target json-schema --out /tmp/out
# WARN [EMIT002] Type 'NoSuchType' cannot be represented without loss
# ...compile still succeeds, exit 0
```

**Reproduction (ambiguous):**

```mdl
domain a { owner: "test"  semantic Code: string }
domain b { owner: "test"  semantic Code: string }
domain c {
  owner: "test"
  entity Thing @ 1 (additive) {
    @key thingId: uuid
    code: Code
  }
}
```

```bash
modelable validate .   # also exits 0, "is valid" - "Code" exists in two domains and is never qualified
```

**Observed:** both cases validate and compile cleanly. The unresolvable case only ever surfaces as an `EMIT002` *warning* ("cannot be represented without loss") at compile time, for targets that need nominal identity — never a `SEM` error. The ambiguous case produces no signal at all, at any stage, in either direction (`modelable resolve`/`modelable lineage` also show it as a plain `named` type with no complaint).

**By contrast**, the *identical* unresolvable/ambiguous situation, when it occurs in a `semantic X: Y` declaration's own underlying-type chain rather than a field's bare type, **is** rejected correctly:

```mdl
semantic BadChain: NoSuchBaseType
# ERROR SEM: ...: semantic type 'BadChain' references unknown semantic type 'NoSuchBaseType'

semantic Wrapper: Code   # with the same a/b domain collision as above
# ERROR SEM: ...: semantic type 'Wrapper' references ambiguous semantic type 'Code'; candidates: a.Code, b.Code
```

**Root cause (read from source, not guessed):** `registry/resolver.py::resolve_semantic_type_ref` does correctly raise `LookupError` (unresolvable) or `AmbiguousSemanticTypeError` (a `LookupError` subclass, by design — see its docstring) in both cases. The semantic-declaration validation path (`validation/semantic.py::_validate_semantic_types`) surfaces whatever it raises as a `SEM` diagnostic. The **field**-type resolution path, however, catches `LookupError` broadly at a higher level and falls back to treating the field as an opaque structural `NamedType` rather than distinguishing "genuinely unresolvable" from "successfully resolved" — so both real errors get silently absorbed into the same fallback that's presumably meant for forward-compatibility with not-yet-parsed constructs.

**Expected:** field-type resolution should report the same `SEM`-level diagnostic that the semantic-declaration path already does, rather than only downgrading to an `EMIT002` warning (and only for unresolvable, never for ambiguous) at compile time for specific targets.

**Showcase workaround:** `tests/conformance/invalid/unknown-semantic.mdl` and `ambiguous-semantic.mdl` both demonstrate the rejection via a `semantic X: Y` chain declaration instead of a plain field reference, since that's the only path that actually produces a diagnostic today. Each file's header comment documents why.

---

## 6. `compile --target protobuf` crashes on reservation reuse instead of diagnosing it

**Status:** Fixed in v1.8.0 via #354 (verified against the 1.8.0 regeneration).

**Discovered:** Task 3.2 (negative fixtures), PR #8.

**Reproduction:**

```mdl
domain probe {
  owner: "test"
  entity Thing @ 1 (additive) {
    @key thingId: uuid
    activeField: string
    reserved protobuf {
      numbers: [2]
      names: ["activeField"]
    }
  }
}
```

```bash
modelable validate .   # exits 0, "is valid" - this check is protobuf-emitter-specific
modelable compile . --target protobuf --out /tmp/out
```

**Observed:**

```text
Traceback (most recent call last):
  ...
  File ".../modelable/emitters/protobuf.py", line 607, in _validate_reservations
    raise ValueError(f"{ref}: field {field.source_name} uses reserved protobuf field number {field.number}")
ValueError: probe.Thing@1: field activeField uses reserved protobuf field number 2
```

Exit code is 1 (correct), and the message is accurate and informative — but it is an unhandled Python exception with a raw traceback, not the tool's normal `ERROR <CODE>: ...` diagnostic format that every other rejection in this log (except #1) uses.

**Expected:** `_emit_target`/`compile_command` should catch this `ValueError` (or the emitter should raise the CLI's own diagnostic type) and print it the same way every other compile-time rejection is printed.

**Showcase workaround:** none needed for correctness — `tests/conformance/invalid/protobuf-reservation-reuse.mdl` and `expected.yaml` assert on the exit code and message text directly (with `code: null`, since there's no clean diagnostic prefix to check), and note this is intentional in a comment.

---

## 7. CEL type-mismatch checking is not implemented

**Status:** Fixed in v1.8.0 via #354 (verified against the 1.8.0 regeneration).

**Discovered:** Task 3.2 (negative fixtures), PR #8. Also documented in `SPEC.md` §13 since it directly explains why `tests/conformance/invalid/` has 17 fixtures rather than 18.

**Reproduction:**

```mdl
domain probe {
  owner: "test"
  entity Thing @ 1 (additive) {
    @key thingId: uuid
    name: string
  }
  projection Broken @ 1
    from probe.Thing @ 1 as t
  {
    thingId <- t.thingId
    broken = t.name > 5
  }
}
```

```bash
modelable validate .
```

**Observed:** `OK ...: is valid.` — comparing a `string` field against an integer literal with `>` produces no diagnostic at all.

**Re-verified against upstream `main`** at commit `e2fe6ac54e6cba42982c5bbeeacad95524393762` (not just the pinned `1.7.0` release): `grep -rn "CEL003\|CEL004\|type.mismatch\|TypeMismatch" cli/src/modelable/expressions/cel.py cli/src/modelable/validation/semantic.py` returns nothing on either version.

**Root cause:** `expressions/cel.py` defines diagnostic codes `CEL001` (parse error), `CEL002` (unknown alias/field), `CEL005` (unsupported function), `CEL006` (aggregate without group by), `CEL007` (non-deterministic function) — the numbering skips `CEL003` and `CEL004` entirely. Reserved-but-unassigned codes in an otherwise densely-numbered sequence strongly suggest type-checking was planned (`CEL003`/`CEL004` reserved for it) and never implemented, rather than intentionally out of scope.

**Expected:** a `CEL003`- or `CEL004`-coded diagnostic when comparison/arithmetic operators are applied to incompatible operand types.

**Showcase workaround:** none — no fixture claims to test this. `SPEC.md` §13 documents the gap directly rather than including a fixture that would validate cleanly while claiming to prove a rejection.

---

## 8. `ref<Model @ >=N <M>>` version-range notation is easy to double-bracket

**Status:** Case C — no upstream code change needed (documentation-only note).

**Discovered:** Task 2.4 (billing/audit/reporting domains), PR #6.

**Reproduction:**

```mdl
other: ref<probe.Thing @ >=1 <3>>
```

```bash
modelable validate .
```

**Observed:**

```text
ERROR PARSE: ...: No terminal matches '>' in the current parser context
other: ref<probe.Thing @ >=1 <3>>
                               ^
```

**Root cause:** not a bug — `version_range` is `">=" INT "<" INT` (four tokens, no bracket of its own), and `ref_type`'s own closing bracket is a *single* trailing `>`. `docs/language-reference.md`'s own table example, `ref<Domain.Model @ >=2 <3>`, is in fact written correctly with one closing `>` — but reading it next to the *unversioned* `ref<Domain.Model>` form makes it easy to assume the range itself needs closing too, producing a doubled `>>` that fails to parse. This is Case C (`UPSTREAM_POLICY.md` §6), not Case A: the design is fine, it's just genuinely easy to misread once, which is exactly what happened while writing `model/billing.mdl`.

**Expected:** nothing needs to change upstream; this entry exists purely so the next person (in this repo or reading this file from outside it) doesn't spend the same few minutes staring at the same lexer error.

**Showcase workaround:** N/A — corrected to the single-bracket form directly; see `model/billing.mdl`'s `Invoice.encounterId` field.

---

## 9. A second `auto projections` declaration for another version of the same model is silently dropped

**Status:** Fixed in v1.8.0 via #354 (verified against the 1.8.0 regeneration).

**Discovered:** Task 3.3 (deferred-capability fixtures), while probing whether `on [...]` operation subsets on `event` auto-projections are visible to `diff`/`lineage` for cross-version comparison.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  entity Thing @ 1 (additive) {
    @key thingId: uuid
    name: string
  }

  entity Thing @ 2 (additive) {
    @key thingId: uuid
    name: string
    extra?: string
  }

  auto projections Thing @ 1 {
    db
    request
    reply
    event on [created]
  }

  auto projections Thing @ 2 {
    db
    request
    reply
    event on [created, deleted]
  }
}
```

```bash
modelable validate .
modelable inspect probe.Thing@1 --auto .
modelable inspect probe.Thing@2 --auto .
```

**Observed:**

```text
$ modelable validate .
OK 3 files valid.

$ modelable inspect probe.Thing@1 --auto .
probe.ThingDb@1 (auto db)
  thingId
  name
probe.ThingRequest@1 (auto request)
  thingId
  name
probe.ThingReply@1 (auto reply)
  thingId
  name
probe.ThingEvent@1 (auto event)
  thingId
  name

$ modelable inspect probe.Thing@2 --auto .
(empty output — no ThingDb@2/ThingRequest@2/ThingReply@2/ThingEvent@2 at all)
```

`validate` reports the file valid with no warning of any kind. Reversing the declaration order in the source (`Thing @ 2`'s `auto projections` block written *before* `Thing @ 1`'s) reverses which version is dropped: version 1's generated projections vanish instead, and version 2's are the ones that materialize. In both orderings, **whichever `auto projections` block appears first in file order wins; the second is discarded entirely**, regardless of which version number it targets. `modelable diff probe.ThingEvent@1 probe.ThingEvent@2` on the first ordering fails outright with `Error: unresolved model reference probe.ThingEvent@2`, since the dropped version's projection was never created to diff against.

**Root cause (read from source, not guessed):** `planner/planner.py::_expand_domain_auto_projections` generates a projection name that is *not* version-qualified (`_generated_projection_name` returns e.g. `"ThingDb"` for every version alike), then guards against overwriting an explicit hand-written projection with:

```python
existing = domain.projections.get(projection_name)
if existing is not None:
    # Skip if an explicit projection with the same name already exists.
    # The workspace validator already checks for conflicts; this is
    # just a safety guard.
    continue
```

`domain.projections[projection_name]` is a *list* of `ProjectionVersion` entries (multiple versions of the same projection name coexist there normally — that's exactly how `ThingDb@1` and `ThingDb@2` are meant to both exist side by side). But this guard only checks whether the key has *any* entries at all, not whether an entry for `decl.version` specifically already exists. After the first `auto projections Thing @ 1` block runs, `domain.projections["ThingDb"]` already has one entry (added via `domain.projections.setdefault(projection_name, []).append(projection)`), so when the second `auto projections Thing @ 2` block runs, `existing is not None` is already true and the whole block is skipped — even though nothing named `ThingDb@2` actually exists yet. The comment's own stated intent ("skip if an *explicit* projection with the same name already exists") is not what the code checks; it skips on *any* prior entry, auto-generated or not, for *any* version.

**Expected:** the guard should check for an entry at `decl.version` specifically (e.g. `any(p.version == decl.version for p in existing)`), not merely `existing is not None`, so that multiple versions of the same model can each get their own auto-generated projections independently, the same way hand-written projection versions already coexist.

**Showcase workaround:** `tests/conformance/deferred/*.mdl` and every canonical domain in `model/` only ever declare one `auto projections <Model> @ <N>` block per model per domain (each real model in this showcase is introduced with auto-projections at its first version and left alone on later additive versions), so the bug is never triggered by the showcase's own deliverables. `tests/conformance/test_deferred_capabilities.py`'s coverage for the `projection-event-operation-coverage-compatibility` deferred capability uses the single-version `scheduling.AppointmentEvent@1` (real, already-shipped model) and its `lineage` output instead of a synthetic multi-version probe, specifically to sidestep this bug rather than let it block that unrelated check. See that test file for detail.

---

## 10. `modelable diff` never reports governance (access/classification/@pii) changes for entities and aggregates, only for projections

**Status:** Fixed in v1.8.0 via #354 (verified against the 1.8.0 regeneration).

**Discovered:** Task 4.1 (model compatibility evolution fixtures), while designing the "classification/access change visibility" case `SPEC.md` §11 requires the compatibility suite to cover.

**Reproduction:**

```mdl
domain probe {
  owner: "test"
  entity Thing @ 1 (additive) {
    @key thingId: uuid
    @pii
    ssn: string

    access {
      entity * [read]
      property ssn admin-team [read, write]
    }
  }
  entity Thing @ 2 (additive) {
    @key thingId: uuid
    @pii
    @classification("restricted")
    ssn: string

    access {
      entity * [read]
      property ssn admin-team [read]
    }
  }
}
```

```bash
modelable diff probe.Thing@1 probe.Thing@2 --path .
```

**Observed:**

```text
probe.Thing@1 -> probe.Thing@2
status: compatible
- no changes
```

Despite `ssn` gaining a `@classification("restricted")` annotation it didn't have before, and the `admin-team` principal losing its `write` grant on `ssn` - both real, meaningful governance changes on the entity itself - `diff` reports nothing at all.

**By contrast**, the *identical* kind of change on a **projection** (`from Thing @ 1 as t { ... }`) *is* correctly detected and reported, including a `breaking: true` classification for the tightening direction:

```text
probe.ThingView@1 -> probe.ThingView@2
status: breaking
- access_grant_removed ssn (governance): access grant removed: ssn principal 'admin-team' permission 'write'
- classification_changed ssn (governance): field 'ssn' classification changed: None -> restricted
```

**Root cause (read from source, not guessed):** `compat/diff.py::_compare_governance(old: ProjectionVersion, new: ProjectionVersion)` implements exactly this comparison (access-grant triples, `@pii`, `@classification`) correctly and completely - but it is only ever called from `compare_projection_versions` (`compat/diff.py` line 637). `compare_model_versions`, the function `check_model_version_compatibility` uses for entity/aggregate/event/value diffs, only ever compares field shape (`compat/diff.py` lines 45+: name, type, optionality, enum values) and index declarations - it never calls `_compare_governance` or anything equivalent, even though `docs/language-reference.md` §10.1 explicitly states "`access` block may appear in a model body and in a projection body," and field-level `@pii`/`@classification` annotations are declared identically in both places syntactically.

**Expected:** `check_model_version_compatibility` should call the same governance-comparison logic `compare_projection_versions` already uses, so a governance change on an entity/aggregate is visible in `diff` output the same way a governance change on a projection already is - the underlying comparison function exists and works, it just isn't wired into both call sites.

**Showcase workaround:** `compat/breaking-v3/patient.mdl` puts its governance-tightening changes (added `@classification("restricted")`, removed `write` grant) on `PatientSummary@3` (a projection) rather than `Patient@3` (the entity), specifically because that's the only place `diff` actually surfaces them. See that file's header comment and `tests/conformance/test_model_compatibility.py::test_breaking_projection_reports_governance_changes`.

---

## 11. `reserved protobuf { names: [...] }` must use the generated snake_case Protobuf name, not the Modelable source field name, for cross-version reuse checks

**Status:** Fixed in v1.8.0 via #354 (verified against the 1.8.0 regeneration).

**Discovered:** Task 4.2 (protobuf/gRPC compatibility fixtures), while building the reservation-safe evolution case `SPEC.md` §11 requires.

**Reproduction:**

```mdl
// old/probe.mdl
domain probe {
  owner: "test"
  entity Thing @ 1 (additive) {
    @key thingId: uuid
    name: string
    legacyNote: string
  }
}
```

```mdl
// new/probe.mdl - legacyNote (Protobuf field 3, proto name legacy_note)
// removed, reserved using its Modelable *source* field name
domain probe {
  owner: "test"
  entity Thing @ 1 (additive) {
    @key thingId: uuid
    name: string
    reserved protobuf {
      numbers: [3]
      names: ["legacyNote"]
    }
  }
}
```

```bash
modelable validate-compat --from old --to new --target protobuf
```

**Observed:**

```text
target: protobuf
status: breaking
- [breaking] removed_field_not_reserved: legacy_note: removed field legacy_note must reserve protobuf number and name
```

Both `new/probe.mdl` and `old/probe.mdl` validate cleanly on their own (`modelable validate` gives no indication anything is wrong with the reservation). Changing only the reservation's spelling to the generated Protobuf name - `names: ["legacy_note"]` (snake_case) instead of `names: ["legacyNote"]` (the Modelable source field name, matching every other identifier's casing convention in the file) - makes the identical scenario report `status: wire_compatible` instead.

**Root cause (read from source, not guessed):** there are two independent reservation-reuse checks in the codebase, and they disagree:

- `emitters/protobuf.py::_validate_reservations` (the same-version, compile-time check - see finding #6 above for its crash-instead-of-diagnostic behavior) compares a candidate field against reservations using **both** spellings: `field.source_name in reserved_names or field.proto_name in reserved_names`.
- `compat/targets.py::_compare_schema` (the cross-version `validate-compat` check this finding is about) reads `reservations.names` from the compiled `schema-manifest.json` - which stores the reservation exactly as typed in `.mdl`, unconverted (`emitters/protobuf.py`'s `reservations=version.protobuf_reservations` passthrough) - and compares it against only `old_field.get("proto_name")`, the *generated* snake_case name. It never also checks the old field's raw source name.

So the two reuse checks accept different spellings of the same reservation, and only one of the two documents which spelling it needs. `docs/language-reference.md`'s own example (`reserved protobuf { names: ["legacy_status"] }`) happens to already use snake_case, but the surrounding prose ("A field... may not reuse a reserved number, source field name, or generated Protobuf field name") reads as if either spelling should work everywhere, which is true for the compile-time check but not the `validate-compat` one.

**Expected:** `compat/targets.py::_compare_schema` should check the old field's raw source name in addition to its proto name (matching `_validate_reservations`'s existing `source_name in reserved_names or proto_name in reserved_names` pattern), so a reservation written in Modelable's normal camelCase convention is honored consistently by both reuse checks.

**Showcase workaround:** `compat/protobuf-safe/new/patient.mdl` writes its reservation as `names: ["legacy_notes"]` (the generated Protobuf name) rather than `names: ["legacyNotes"]` (the Modelable source field name used everywhere else in that same file) specifically so `validate-compat` recognizes it - see that file's header comment.

---

## 12. `compile --target typescript` never imports a field's semantic type - every semantic-typed field is a compile error

**Status:** Fixed in v1.8.0 via #354 (verified against the 1.8.0 regeneration; the `apps/web/src/generated-types.ts` workaround for #12/#13 was removed once the pin moved).

**Discovered:** Task 6.1 (bootstrap React application), while satisfying the task's own requirement that the app build imports and compiles a real generated Patient type.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  semantic ThingId: uuid(7) {
    registry: true
  }

  entity Thing @ 1 (additive) {
    @key
    thingId: ThingId
  }
}
```

```bash
modelable compile . --target typescript --out ./dist
npx tsc --noEmit --strict ./dist/probe.Thing.v1.ts
```

**Observed:**

```text
$ modelable compile . --target typescript --out ./dist
WARN [EMIT003] Missing metadata required by target: probe.Thing.thingId
OK ./dist/probe.Thing.v1.ts ...

$ cat ./dist/probe.Thing.v1.ts
export interface ProbeThingV1 {
  thingId: ThingId;
}
export type Thing = ProbeThingV1;

$ npx tsc --noEmit --strict ./dist/probe.Thing.v1.ts
probe.Thing.v1.ts(12,12): error TS2552: Cannot find name 'ThingId'. Did you mean 'Thing'?
```

`ThingId` is referenced but never imported or declared anywhere in the file - a real, unhandled `tsc` compile error, not a lint warning. `EMIT003` fires at compile time but is only a warning; the CLI still writes broken code with exit 0. This affects essentially every entity/aggregate/event in a realistic Modelable workspace, since `@key` fields are conventionally semantic types (this showcase's own `patient.Patient.v2.ts` fails identically on its `patientId: PatientId` field).

**Root cause (read from source, not guessed):** `emitters/typescript.py::_collect_named_imports` resolves a field's bare `NamedType` reference to an import only by searching `domain.models` (`DomainDef.models: dict[str, list[ModelVersion]]`, populated by `entity`/`aggregate`/`event`/`value` declarations):

```python
def _collect_named_imports(field_type, mdl, named_imports: dict[str, tuple[str, str]]) -> None:
    if isinstance(field_type, NamedType):
        name = field_type.name
        if name not in named_imports and mdl is not None:
            for domain in mdl.domains:
                if name in domain.models:
                    ...
```

`semantic` declarations live in a structurally separate field, `DomainDef.semantic_types: list[SemanticTypeDecl]`, which this function never consults. So a semantic type is never resolved to an import, and the field is emitted as a bare, undeclared type name. (Value types, by contrast, *are* stored in `domain.models` alongside entities/aggregates/events, which is why `patient.Patient.v2.ts`'s `contact: ContactDetails` and `address?: Address` fields import correctly while `patientId: PatientId` on the very next line does not.)

**Expected:** `_collect_named_imports` should also search each domain's `semantic_types`, either importing a dedicated semantic-type file (if one is ever emitted for TypeScript - none currently is, unlike Rust's per-semantic-type file) or emitting the underlying type inline the way `EMIT002`'s "cannot be represented without loss" already signals elsewhere. Either way, the generated file must not reference an undefined name.

**Showcase workaround:** none that avoids touching generated output (`UPSTREAM_POLICY.md` §1 forbids post-processing generated files or shimming around a compile-breaking emitter bug as a permanent fix). `apps/web` imports `patient.ContactDetails.v0.ts`/`patient.Address.v0.ts` (patient-domain value types with no semantic-typed fields, which compile as-is) instead of the broken `patient.Patient.v2.ts`/`patient.PatientDb.v2.ts` - see `apps/web/src/generated-types.ts`'s header comment. The user has taken ownership of the upstream fix as a separate, dedicated task; this workaround is meant to be temporary until Modelable is re-pinned past a release that fixes it.

---

## 13. `compile --target typescript` never emits any imports at all for auto-generated projections (Db/Request/Reply/Event)

**Status:** Fixed in v1.8.0 via #354 (verified against the 1.8.0 regeneration).

**Discovered:** Task 6.1 (bootstrap React application), alongside finding #12.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  value Note {
    text: string
  }

  entity Thing @ 1 (additive) {
    @key
    thingId: uuid
    note: Note
  }

  auto projections Thing @ 1 {
    db
  }
}
```

```bash
modelable compile . --target typescript --out ./dist
npx tsc --noEmit --strict ./dist/probe.ThingDb.v1.ts
```

**Observed:**

```text
$ cat ./dist/probe.ThingDb.v1.ts
export interface ProbeThingDbV1 {
  thingId: string;
  note: Note;
}
export type ThingDb = ProbeThingDbV1;

$ npx tsc --noEmit --strict ./dist/probe.ThingDb.v1.ts
probe.ThingDb.v1.ts(11,9): error TS2304: Cannot find name 'Note'.
```

Zero `import` statements anywhere in the file, even though `Note` is a plain `value` type that *does* import correctly on the entity file (`probe.Thing.v1.ts`) it was auto-projected from. This is strictly worse than finding #12: every field type that would need an import - value types, semantic types, everything - is broken on every projection-kind artifact, which is the majority of files this target emits (every `Db`/`Request`/`Reply`/`Event` auto-projection, plus every hand-written `projection {}`).

**Root cause (read from source, not guessed):** `emitters/typescript.py::_emit_model` (used for entities/aggregates/events/values) calls `_collect_ref_imports`/`_collect_named_imports` before rendering fields, and prepends the resulting `import_lines` to the file. `_emit_projection` (used for every projection, auto-generated or explicit) has no equivalent call anywhere in its body - it renders each field's type directly via `_type_to_ts(field_type, wire_targets=...)` with no `resolved_refs`/`named_imports` collected first, so the import-emission logic that exists in the codebase simply never runs for this code path.

**Expected:** `_emit_projection` should collect and emit imports the same way `_emit_model` already does - the logic to do so already exists and works correctly; it just isn't called from this second function.

**Showcase workaround:** none that avoids touching generated output, same reasoning as finding #12. `apps/web` avoids importing any projection-kind (`Db`/`Request`/`Reply`/`Event`/custom `projection`) TypeScript artifact until this is fixed upstream - see `apps/web/src/generated-types.ts`'s header comment.

---

## 14. `compile --target rust` loses named-type resolution for optional array fields specifically

**Status:** Fixed in v1.8.0 via [ktjn/modelable#355](https://github.com/ktjn/modelable/pull/355) (verified against the 1.8.0 regeneration: `generated/rust/clinical-core` now compiles cleanly, so the rust flip assertion was updated).

**Discovered:** Task 7.1 (Rust generated package build), running real `cargo check` against the generated multi-package workspace for the first time in this plan.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  value Note {
    text: string
  }

  entity Thing @ 1 (additive) {
    @key thingId: uuid
    optionalNotes?: array<Note>
    requiredNotes: array<Note>
  }
}
```

```bash
modelable compile . --target rust --out ./dist
cd ./dist/probe && cargo check
```

**Observed:**

```rust
// dist/probe/probe_thing_v1.rs
use super::probe_note_v0::ProbeNoteV0;

pub struct ProbeThingV1 {
    pub thing_id: uuid::Uuid,
    #[serde(default)]
    pub optional_notes: Vec<Note>,       // <- undefined, should be Vec<ProbeNoteV0>
    pub required_notes: Vec<ProbeNoteV0>, // <- correct
}
```

```text
error[E0425]: cannot find type `Note` in this scope
```

Identical field shape (`array<Note>`), only the optionality differs - the required version resolves correctly, the optional version doesn't. This showcase's own `clinical.Encounter.diagnoses?: array<Diagnosis>` field hits this exact bug (`Vec<Diagnosis>` instead of `Vec<ClinicalDiagnosisV0>`), which is enough to break `cargo check` on the real `clinical-core` package and, transitively, `billing-core` (which depends on it) - two of this showcase's three generated Rust packages fail to compile out of the box.

**Root cause (read from source, not guessed):** `emitters/rust.py::_field_specs_from_model_fields` renders each field's type via `_shape_annotation(shape, ..., named_type_map=named_type_map)`, which correctly threads `named_type_map` through array/map/named recursion. But for the specific case of an *optional* array field, the function takes a second pass to switch the field from `Option<Vec<T>>` to a plain `Vec<T>` + `#[serde(default)]` (documented in an inline comment: "Optional arrays use Vec<T> + #[serde(default)] - Option<Vec<T>> forces unwrap before iteration"), and *recomputes* the annotation with a **second call** to `_shape_base_annotation(shape, owner_type=..., path=..., definitions=..., rust_hint=wire.get("rust"))` - which omits both `named_type_map=named_type_map` and `enum_info=enum_info`, even though `_shape_base_annotation`'s own signature accepts both. Losing `named_type_map` means the array's named-type item falls through to `_pascalize(shape.ref or "Named")` (the "nothing resolved" fallback) instead of the correct stable type name; losing `enum_info` likely has an analogous effect for `array<enum(...)>?` fields, not separately reproduced here but sharing the identical root cause.

**Expected:** the second `_shape_base_annotation` call in the optional-array branch should pass `named_type_map=named_type_map, enum_info=enum_info`, matching every other call site.

**Showcase workaround:** none that avoids touching generated output (`UPSTREAM_POLICY.md` §1). This blocks the `clinical-core`/`billing-core` `cargo check` half of Task 7.1's acceptance criteria until fixed upstream.

---

## 15. `compile --target csharp` never resolves named-type references to the emitted stable type name - every value-type-typed field is a compile error

**Status:** Fixed in v1.8.0 via [ktjn/modelable#365](https://github.com/ktjn/modelable/pull/365) for same-namespace references. Cross-namespace (cross-domain) references still do not compile — that residual is tracked as a new finding, [## 28](#28-compile---target-csharp-never-imports-or-qualifies-types-from-another-domain---cross-domain-field-references-are-still-compile-errors).

**Discovered:** Task 7.2 (C# probe), running the first real `dotnet build` against generated `csharp` output.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  value Address {
    street: string
  }

  entity Widget @ 1 (additive) {
    @key id: uuid
    addr?: Address
  }
}
```

```bash
modelable compile . --target csharp --out ./dist
dotnet build ./consumer   # a project that compiles every file in ./dist
```

**Observed:**

```text
// dist/probe.Address.v0.cs
public sealed record ProbeAddressV0
{
    public required string Street { get; init; }
}

// dist/probe.Widget.v1.cs
public sealed record ProbeWidgetV1
{
    public required Guid Id { get; init; }
    public Address? Addr { get; init; }   // <- undefined, defined as ProbeAddressV0
}

error CS0246: The type or namespace name 'Address' could not be found
```

The value type `Address` **is** emitted - under the stable prefixed name `ProbeAddressV0` - but the entity field that references it emits the short source name `Address`. Same-namespace, same compile unit, and the two names never agree, so every field whose type is a `value` declaration is a compile error. This is the majority of the C# output: this showcase's own `patient.Patient.v2.cs` (`Address? Address`, `ContactDetails Contact`), `scheduling.Appointment.v1.cs` (`TimeRange Slot`), `billing.Invoice.v2.cs` (`List<InvoiceLine> Lines`), `clinical.EncounterDb.v1.cs` (`List<Diagnosis>? Diagnoses`), and every projection derived from them fail identically. Only self-contained value types with no references (`patient.Address.v0.cs`/`PatientAddressV0`, `scheduling.TimeRange.v0.cs`/`SchedulingTimeRangeV0`, `billing.InvoiceLine.v0.cs`/`BillingInvoiceLineV0`, `clinical.Diagnosis.v0.cs`/`ClinicalDiagnosisV0`, `patient.ContactDetails.v0.cs`/`PatientContactDetailsV0`) compile as-is.

**Root cause (read from source, not guessed):** `emitters/csharp.py::_shape_base_to_csharp` renders every `named`-kind shape as `_pascalize(shape.ref or "Named")` (line 186) - the raw short source name from the `.mdl` file, with no lookup into what the emitter actually named the declaration. That differs from `emitters/rust.py`, which threads a `named_type_map` through its shape rendering so a reference is rewritten to the *emitted* stable name (`PatientAddressV0` etc.); the C# emitter has no equivalent map at all. The definitions are emitted correctly elsewhere (`_stable_type_name(domain, name, version)` produces `ProbeAddressV0`), so reference and definition simply disagree by construction. Cross-domain value references are worse in a different way (see finding #16's reproduction for the cross-domain spelling), and nothing upstream checks for this: `cli/tests/test_emit_csharp.py` asserts only on generated *text substrings* for primitives and inline `object {}` shapes and never compiles the output or references a declared `value`/`semantic` type, so the compile-breaking reference mismatch is invisible to the upstream suite.

**Expected:** `_shape_base_to_csharp`'s `named` branch should resolve `shape.ref` to the emitted stable type name the same way the Rust emitter's `named_type_map` does, so the referenced name always matches the emitted definition. A small regression test that compiles the generated output (or at least asserts the reference name equals `_stable_type_name(...)` for a declared value type) would keep it fixed.

**Showcase workaround:** `probes/csharp/` (Task 7.2) links only the five self-contained value types that compile as-is and documents the rest as broken - mirroring `apps/web/src/generated-types.ts`'s treatment of findings #12/#13. See `probes/csharp/ModelableShowcase.Probe.csproj`'s header comment; `tests/integration/test_csharp_codegen.py` asserts the full-set failure explicitly so it flips when the emitter is fixed.

---

## 16. `compile --target csharp` never emits semantic types at all - every semantic-typed field is a compile error

**Status:** Fixed in v1.8.0 via #365 for same-namespace references (semantic types are now emitted and resolved). Cross-namespace residuals tracked in [## 28](#28-compile---target-csharp-never-imports-or-qualifies-types-from-another-domain---cross-domain-field-references-are-still-compile-errors).

**Discovered:** Task 7.2 (C# probe), alongside finding #15.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  semantic ThingId: uuid(7) {
    registry: true
  }

  entity Widget @ 1 (additive) {
    @key
    id: ThingId
  }
}
```

```bash
modelable compile . --target csharp --out ./dist
dotnet build ./consumer   # a project that compiles every file in ./dist
```

**Observed:**

```text
$ ls ./dist
probe.Widget.v1.cs   # <- the only file; no probe.ThingId.cs anywhere

$ cat ./dist/probe.Widget.v1.cs
public sealed record ProbeWidgetV1
{
    public required ThingId Id { get; init; }   // <- referenced, never declared or emitted
}

error CS0246: The type or namespace name 'ThingId' could not be found
```

`ThingId` is referenced but no definition file is ever emitted - unlike `emitters/rust.py`, which emits one `*_id.rs` file per `semantic` declaration (carrying the `REGISTRY_ID` constant). The C# emitter emits exactly one file per model/projection and nothing for semantic types. This affects essentially every entity/aggregate/event in a realistic workspace (this showcase's own `patient.Patient.v2.cs` fails on its `@key patientId: PatientId`, `scheduling.Appointment.v1.cs` on `PractitionerId`/`AppointmentId`, `clinical.EncounterDb.v1.cs` on `EncounterId`, `billing.Invoice.v2.cs` on `InvoiceId`, `clinical.Observation.v1.cs` on `ObservationCode`). Cross-domain semantic references (`patientId: patient.PatientId` in clinical/billing) get spelled `PatientPatientId` - the whole dotted reference is pascalized in place - which is a second, equally-undefined name.

**Root cause (read from source, not guessed):** `emitters/csharp.py::emit_csharp` (lines 17-24) iterates only `domain.models` (entities/aggregates/events/values) and `domain.projections`. It never iterates `domain.semantic_types`, and unlike `emitters/rust.py::_emit_semantic_type` there is no C# semantic-type emitter at all - nothing produces a `ThingId` record or resolves the reference structurally to the underlying `Guid`. The `named`-kind shape for a semantic-typed field therefore falls through to the same `_pascalize(shape.ref)` fallback as finding #15, yielding a bare undefined name. (`cli/tests/test_emit_csharp.py` never uses a `semantic` declaration, so upstream has no test that would catch it.)

**Expected:** emit a semantic type for the C# target (e.g. a record wrapping the underlying type, mirroring Rust's per-semantic-type artifact, or at minimum the underlying primitive inline with the `EMIT002` "cannot be represented without loss" warning) and resolve field references to it - the generated file must not reference an undefined name, and `@key` fields on real entities must compile.

**Showcase workaround:** none that avoids touching generated output (`UPSTREAM_POLICY.md` §1), same as findings #12/#13. `probes/csharp/` deliberately does not link any artifact containing a semantic-typed field and documents why; `tests/integration/test_csharp_codegen.py` asserts the current failure explicitly. Until one of these two findings is fixed upstream, the C# target cannot compile any realistic Modelable workspace.

---

## 17. `compile --target java` never resolves named-type references to the emitted stable type name - every value-type-typed field is a compile error

**Status:** Fixed in v1.8.0 via #365 for same-package references. Cross-package (cross-domain) references still do not compile — tracked as a new finding, [## 29](#29-compile---target-java-never-imports-or-qualifies-types-from-another-domain---cross-domain-field-references-are-still-compile-errors).

**Discovered:** Task 7.3 (Java probe), running the first real `javac` against generated `java` output.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  value Address {
    street: string
  }

  entity Widget @ 1 (additive) {
    @key id: uuid
    addr?: Address
  }
}
```

```bash
modelable compile . --target java --out ./dist
javac --release 21 -d ./classes dist/**/*.java
```

**Observed:**

```text
// dist/probe/AddressV0.java
public record AddressV0(
    String street
) {
}

// dist/probe/WidgetV1.java
public record WidgetV1(
    UUID id,
    Optional<Address> addr      // <- undefined, defined as AddressV0
) {
}

WidgetV1.java:9: error: cannot find symbol
    Optional<Address> addr,
                  ^
  symbol:   class Address
```

The value type `Address` **is** emitted - under `_type_name(model_name, version)` = `AddressV0` - but the entity field that references it emits the short source name `Address`. Same package, same compile unit, and the two names never agree, so every field whose type is a `value` declaration is a compile error. This is the majority of the Java output: `javac` over this showcase's full `generated/java/` reports `cannot find symbol` for `Address`, `ContactDetails`, `TimeRange`, `InvoiceLine`, and `Diagnosis` (436 total error lines). Only self-contained value types with no references (`patient/AddressV0.java`, `patient/ContactDetailsV0.java`, `scheduling/TimeRangeV0.java`, `billing/InvoiceLineV0.java`, `clinical/DiagnosisV0.java`) compile as-is.

**Root cause (read from source, not guessed):** `emitters/java.py::_shape_base_to_java` renders every `named`-kind shape as `_pascalize(shape.ref or "Named")` (line 207) - the raw short source name from the `.mdl` file, with no lookup into what the emitter actually named the declaration. That differs from `emitters/rust.py`, which threads a `named_type_map` through its shape rendering so a reference is rewritten to the *emitted* stable name (`PatientAddressV0` etc.); the Java emitter has no equivalent map at all. The definitions are emitted correctly elsewhere (`_type_name(model_name, version)` produces `AddressV0`), so reference and definition simply disagree by construction. Nothing upstream checks for this: `cli/tests/test_emit_java.py` asserts only on generated *text substrings* for primitives, inline `object {}` shapes (which the emitter names after the field and emits as a nested record inside the same file, so they agree), and decimal/binary/temporal types - it never compiles the output or references a declared `value` type, so the compile-breaking reference mismatch is invisible to the upstream suite.

**Expected:** `_shape_base_to_java`'s `named` branch should resolve `shape.ref` to the emitted stable type name the same way the Rust emitter's `named_type_map` does, so the referenced name always matches the emitted definition. A small regression test that compiles the generated output (or at least asserts the reference name equals `_type_name(name, version)` for a declared value type) would keep it fixed.

**Showcase workaround:** `probes/java/` (Task 7.3) compiles only the five self-contained value types that work as-is and documents the rest as broken - mirroring `probes/csharp/`'s treatment of findings #15/#16 and `apps/web/src/generated-types.ts`'s treatment of #12/#13. See `probes/java/pom.xml`'s header comment; `tests/integration/test_java_codegen.py` asserts the full-set failure explicitly so it flips when the emitter is fixed.

---

## 18. `compile --target java` never emits semantic types at all - every semantic-typed field is a compile error

**Status:** Fixed in v1.8.0 via #365 for same-package references (semantic types are now emitted and resolved). Cross-package residuals tracked in [## 29](#29-compile---target-java-never-imports-or-qualifies-types-from-another-domain---cross-domain-field-references-are-still-compile-errors).

**Discovered:** Task 7.3 (Java probe), alongside finding #17.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  semantic ThingId: uuid(7) {
    registry: true
  }

  entity Widget @ 1 (additive) {
    @key
    id: ThingId
  }
}
```

```bash
modelable compile . --target java --out ./dist
javac --release 21 -d ./classes dist/**/*.java
```

**Observed:**

```text
$ ls ./dist/probe
WidgetV1.java        # <- the only file; no ThingId.java anywhere

$ cat ./dist/probe/WidgetV1.java
public record WidgetV1(
    ThingId id,       // <- referenced, never declared or emitted
) {
}

WidgetV1.java:6: error: cannot find symbol
    ThingId id,
    ^
  symbol:   class ThingId
```

`ThingId` is referenced but no definition file is ever emitted - unlike `emitters/rust.py`, which emits one `*_id.rs` file per `semantic` declaration (carrying the `REGISTRY_ID` constant). The Java emitter emits exactly one file per model/projection and nothing for semantic types. This affects essentially every entity/aggregate/event in a realistic workspace (this showcase's own `patient/PatientV2.java` fails on its `@key patientId: PatientId`, `scheduling/AppointmentV1.java` on `AppointmentId`/`PractitionerId`, `clinical/EncounterDbV1.java` on `EncounterId`, `billing/InvoiceV2.java` on `InvoiceId`, `clinical/ObservationV1.java` on `ObservationCode`). Cross-domain semantic references (`patientId: patient.PatientId` in clinical/billing) get spelled `PatientPatientId` - the whole dotted reference is pascalized in place - which is a second, equally-undefined name (`SchedulingPractitionerId` appears the same way).

**Root cause (read from source, not guessed):** `emitters/java.py::emit_java` (lines 16-23) iterates only `domain.models` (entities/aggregates/events/values) and `domain.projections`. It never iterates `domain.semantic_types`, and unlike `emitters/rust.py::_emit_semantic_type` there is no Java semantic-type emitter at all - nothing produces a `ThingId` record or resolves the reference structurally to the underlying `UUID`. The `named`-kind shape for a semantic-typed field therefore falls through to the same `_pascalize(shape.ref)` fallback as finding #17, yielding a bare undefined name. (`cli/tests/test_emit_java.py` never uses a `semantic` declaration, so upstream has no test that would catch it.)

**Expected:** emit a semantic type for the Java target (e.g. a record wrapping the underlying type, mirroring Rust's per-semantic-type artifact, or at minimum the underlying primitive inline with the `EMIT002` "cannot be represented without loss" warning) and resolve field references to it - the generated file must not reference an undefined name, and `@key` fields on real entities must compile.

**Showcase workaround:** none that avoids touching generated output (`UPSTREAM_POLICY.md` §1), same as findings #12/#13/#15/#16. `probes/java/` deliberately does not compile any artifact containing a semantic-typed field and documents why; `tests/integration/test_java_codegen.py` asserts the current failure explicitly. Until one of these two findings is fixed upstream, the Java target cannot compile any realistic Modelable workspace.

---

## 19. `compile --target python` never resolves named-type references to the emitted stable type name - every value-type-typed annotation is a NameError

**Status:** Partially fixed in v1.8.0 via #365: the specific *naming mismatch* this finding describes (annotation uses the short source name, e.g. `Address`, while the definition is emitted under the stable name, e.g. `ProbeAddressV0`) is gone - re-verified against v1.9.4, every reference now correctly names the stable type (`generated/python/patient/patient_patient_v2.py` declares `contact: PatientContactDetailsV0`, matching the real class name in `patient_contact_details_v0.py`). **But this does not mean value-type annotations resolve** - see [## 30](#30-compile---target-python-never-imports-referenced-types-from-other-modules---annotations-still-do-not-resolve-cross-module), whose corrected status (below) shows the module simply never imports the sibling file that defines the now-correctly-named type, same-domain references included, not just cross-domain ones as originally scoped.

**Discovered:** Task 7.4 (Python probe), running the first real annotation-resolution (`typing.get_type_hints`) against generated `python` output.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  value Address {
    street: string
  }

  entity Widget @ 1 (additive) {
    @key id: uuid
    addr?: Address
  }
}
```

```bash
modelable compile . --target python --out ./dist
python -c "import probe_widget_v1, typing; typing.get_type_hints(probe_widget_v1.ProbeWidgetV1)"
```

**Observed:**

```text
// dist/probe/probe_address_v0.py
@dataclass(frozen=True, slots=True)
class ProbeAddressV0:
    street: str

// dist/probe/probe_widget_v1.py
@dataclass(frozen=True, slots=True)
class ProbeWidgetV1:
    id: ThingId
    addr: Optional[Address] = None

$ python -c "import probe_widget_v1, typing; typing.get_type_hints(probe_widget_v1.ProbeWidgetV1)"
NameError: name 'ThingId' is not defined
```

The value type `Address` **is** emitted - under the stable prefixed name `ProbeAddressV0` - but the entity field that references it emits the short source name `Address` in its annotation. Same directory, same import universe, and the two names never agree, so resolving the annotation on any field whose type is a `value` declaration raises `NameError` (as does any semantic-typed field - see finding #20). Every entity/projection annotation that references a value type is affected: this showcase's own `PatientPatientV2` (`contact: ContactDetails`, `address: Optional[Address]`), `SchedulingAppointmentV1` (`slot: TimeRange`), `BillingInvoiceV2` (`lines: list[InvoiceLine]`), `ClinicalEncounterDbV1` (`diagnoses: list[Diagnosis]`), and so on. Only self-contained value types with no references (`ProbeAddressV0`/`ProbeContactDetailsV0`/`ProbeTimeRangeV0`/`ProbeInvoiceLineV0`/`ProbeDiagnosisV0`) resolve cleanly.

**Root cause (read from source, not guessed):** `emitters/python.py::_shape_base_annotation` renders every `named`-kind shape as `_pascalize(shape.ref or "Named")` (line 221) - the raw short source name from the `.mdl` file, with no lookup into what the emitter actually named the declaration. That differs from `emitters/rust.py`, which threads a `named_type_map` through its shape rendering so a reference is rewritten to the *emitted* stable name (`PatientAddressV0` etc.); the Python emitter has no equivalent map at all. The definitions are emitted correctly elsewhere (`_stable_type_name(domain, name, version)` produces `ProbeAddressV0`), so reference and definition simply disagree by construction. The breakage is *latent* rather than a hard error because `_header_lines()` unconditionally emits `from __future__ import annotations` - annotations are stored as strings and nothing resolves them at class-definition time - so the module imports and the dataclass instantiates normally; the `NameError` only appears when an annotation is resolved (`typing.get_type_hints`, `inspect`, pydantic, static type checkers, IDE hover, etc.). Nothing upstream checks for this: `cli/tests/test_emit_python.py` asserts only on generated *text substrings* for primitives and never resolves an annotation or references a declared `value` type, so the mismatch is invisible to the upstream suite.

**Expected:** `_shape_base_annotation`'s `named` branch should resolve `shape.ref` to the emitted stable type name the same way the Rust emitter's `named_type_map` does - and ideally the emitter should emit the real cross-module imports its own annotations imply (it emits *no* `from ... import` lines at all, relying entirely on `from __future__ import annotations` to defer resolution), so a consumer can resolve `get_type_hints` without first constructing a bespoke import graph. A small regression test that resolves the generated annotations (or at least asserts the reference name equals `_stable_type_name(...)` for a declared value type) would keep it fixed.

**Showcase workaround:** `probes/python/` (Task 7.4) imports and instantiates every generated module directly (which works today thanks to the lazy annotations) and serializes the working value types, but asserts the current `get_type_hints` failure on entity/projection classes explicitly so it flips when the emitter is fixed. See `probes/python/test_generated.py`'s header comment; `tests/integration/test_python_codegen.py` mirrors the flip signal.

---

## 20. `compile --target python` never emits semantic types at all - every semantic-typed annotation is a NameError

**Status:** Fixed in v1.8.0 via #365 for same-module references (semantic types are now emitted and resolved within a module). Cross-module residuals tracked in [## 30](#30-compile---target-python-never-imports-referenced-types-from-other-modules---annotations-still-do-not-resolve-cross-module).

**Discovered:** Task 7.4 (Python probe), alongside finding #19.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  semantic ThingId: uuid(7) {
    registry: true
  }

  entity Widget @ 1 (additive) {
    @key
    id: ThingId
  }
}
```

```bash
modelable compile . --target python --out ./dist
python -c "import probe_widget_v1, typing; typing.get_type_hints(probe_widget_v1.ProbeWidgetV1)"
```

**Observed:**

```text
$ ls ./dist/probe
probe_address_v0.py   # (from the reproduction in finding #19)
probe_widget_v1.py    # <- no probe_thing_id.py anywhere

$ python -c "import probe_widget_v1, typing; typing.get_type_hints(probe_widget_v1.ProbeWidgetV1)"
NameError: name 'ThingId' is not defined
```

`ThingId` appears in the `id` field's annotation but no definition module is ever emitted - unlike `emitters/rust.py`, which emits one `*_id.rs` file per `semantic` declaration (carrying the `REGISTRY_ID` constant). The Python emitter emits exactly one module per model/projection and nothing for semantic types. This affects essentially every entity/aggregate/event in a realistic workspace (this showcase's own `PatientPatientV2` fails on its `@key patientId: PatientId`, `SchedulingAppointmentV1` on `AppointmentId`/`PractitionerId`, `ClinicalEncounterDbV1` on `EncounterId`, `BillingInvoiceV2` on `InvoiceId`, `ClinicalObservationV1` on `ObservationCode`). Cross-domain semantic references (`patientId: patient.PatientId` in clinical/billing) get spelled `PatientPatientId` - the whole dotted reference is pascalized in place - which is a second, equally-undefined name (`SchedulingPractitionerId` appears the same way). As with finding #19 this is latent: the module imports and instantiates fine, and the `NameError` surfaces only on annotation resolution.

**Root cause (read from source, not guessed):** `emitters/python.py::emit_python` (lines 16-31) iterates only `domain.models` (entities/aggregates/events/values) and `domain.projections`. It never iterates `domain.semantic_types`, and unlike `emitters/rust.py::_emit_semantic_type` there is no Python semantic-type emitter at all - nothing produces a `ThingId` module or resolves the reference structurally to the underlying `UUID`. The `named`-kind shape for a semantic-typed field therefore falls through to the same `_pascalize(shape.ref)` fallback as finding #19, yielding a bare undefined name in the annotation. (`cli/tests/test_emit_python.py` never uses a `semantic` declaration, so upstream has no test that would catch it.)

**Expected:** emit a semantic type for the Python target (e.g. a module wrapping the underlying type, mirroring Rust's per-semantic-type artifact, or at minimum the underlying primitive inline with the `EMIT002` "cannot be represented without loss" warning) and resolve field references to it - the generated annotation must not reference an undefined name, and `@key` fields on real entities must survive `get_type_hints`.

**Showcase workaround:** none that avoids touching generated output (`UPSTREAM_POLICY.md` §1), same as findings #12/#13/#15/#16/#18. `probes/python/` instantiates the generated dataclasses directly (valid today) but deliberately does not rely on resolving semantic-typed annotations, and `tests/integration/test_python_codegen.py` asserts the current `NameError` explicitly. Until one of these two findings is fixed upstream, the Python target's annotations cannot be consumed by any typed tooling.

---

## 21. `compile --target go` never resolves named-type references to the emitted stable type name - every value-type-typed field is a compile error

**Status:** Fixed in v1.8.0 via #365 for same-package references. Cross-package (cross-domain) references still do not compile — tracked as a new finding, [## 31](#31-compile---target-go-never-imports-or-qualifies-types-from-another-package---cross-domain-field-references-are-still-compile-errors).

**Discovered:** Task 7.4 (Go probe), running the first real `go build` against generated `go` output.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  value Address {
    street: string
  }

  entity Widget @ 1 (additive) {
    @key id: uuid
    addr?: Address
  }
}
```

```bash
modelable compile . --target go --out ./dist
# dist/go/probe has no go.mod; init a throwaway module around it, then:
cd ./dist && go build ./...
```

**Observed:**

```text
// dist/probe/probe_address_v0.go
type ProbeAddressV0 struct {
    Street string `json:"street"`
}

// dist/probe/probe_widget_v1.go
type ProbeWidgetV1 struct {
    Id ThingId `json:"id"`
    Addr *Address `json:"addr,omitempty"`
}

# probe/probe
probe\probe_widget_v1.go:5:8: undefined: ThingId
probe\probe_widget_v1.go:6:11: undefined: Address
```

The value type `Address` **is** emitted - under the stable prefixed name `ProbeAddressV0` - but the entity struct that references it emits the short source name `Address`. Same package, same compile unit, and the two names never agree, so every field whose type is a `value` declaration is a compile error. This is the majority of the Go output: `go build` over this showcase's full `generated/go/` reports 48 `undefined:` error lines for `Address`, `ContactDetails`, `TimeRange`, `InvoiceLine`, and `Diagnosis` (plus the semantic-typed names from finding #22 - the missing-symbol set is identical to Java's). Go's whole-package compilation means not even the self-contained value types can be built on their own in their original packages (each domain package also contains a struct that references the undefined names), though the value-type files themselves are valid Go in isolation.

**Root cause (read from source, not guessed):** `emitters/go.py::_shape_base_annotation` renders every `named`-kind shape as `_pascalize(shape.ref or "Named")` (line 288) - the raw short source name from the `.mdl` file, with no lookup into what the emitter actually named the declaration. That differs from `emitters/rust.py`, which threads a `named_type_map` through its shape rendering so a reference is rewritten to the *emitted* stable name (`PatientAddressV0` etc.); the Go emitter has no equivalent map at all. The definitions are emitted correctly elsewhere (`_stable_type_name(domain, name, version)` produces `ProbeAddressV0`), so reference and definition simply disagree by construction. Nothing upstream checks for this: `cli/tests/test_emit_go.py` asserts only on generated *text substrings* for primitives and never compiles the output or references a declared `value` type, so the compile-breaking reference mismatch is invisible to the upstream suite.

**Expected:** `_shape_base_annotation`'s `named` branch should resolve `shape.ref` to the emitted stable type name the same way the Rust emitter's `named_type_map` does, so the referenced name always matches the emitted definition. A small regression test that compiles the generated output (or at least asserts the reference name equals `_stable_type_name(...)` for a declared value type) would keep it fixed.

**Showcase workaround:** `probes/go/` (Task 7.4) builds the five self-contained value-type source files verbatim into a throwaway module whose package layout lets them compile and be exercised (Go compiles whole packages, so the probe reassembles the value types into packages that contain only their own declarations - no generated file is edited or copied into git), and documents the rest as broken. See `probes/go/generated_test.go`'s header comment; `tests/integration/test_go_codegen.py` asserts the full-set failure explicitly so it flips when the emitter is fixed.

---

## 22. `compile --target go` never emits semantic types at all - every semantic-typed field is a compile error

**Status:** Fixed in v1.8.0 via #365 for same-package references (semantic types are now emitted and resolved within a package). Cross-package residuals tracked in [## 31](#31-compile---target-go-never-imports-or-qualifies-types-from-another-package---cross-domain-field-references-are-still-compile-errors).

**Discovered:** Task 7.4 (Go probe), alongside finding #21.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  semantic ThingId: uuid(7) {
    registry: true
  }

  entity Widget @ 1 (additive) {
    @key
    id: ThingId
  }
}
```

```bash
modelable compile . --target go --out ./dist
cd ./dist && go build ./...
```

**Observed:**

```text
$ ls ./dist/probe
probe_widget_v1.go     # <- no probe_thing_id.go anywhere

$ cat ./dist/probe/probe_widget_v1.go
type ProbeWidgetV1 struct {
    Id ThingId `json:"id"`
}

# probe/probe
probe\probe_widget_v1.go:5:8: undefined: ThingId
```

`ThingId` is referenced but no definition file is ever emitted - unlike `emitters/rust.py`, which emits one `*_id.rs` file per `semantic` declaration (carrying the `REGISTRY_ID` constant). The Go emitter emits exactly one file per model/projection and nothing for semantic types. This affects essentially every entity/aggregate/event in a realistic workspace (this showcase's own `patient/patient_patient_v2.go` fails on its `@key patientId: PatientId`, `scheduling/scheduling_appointment_v1.go` on `AppointmentId`/`PractitionerId`, `clinical/clinical_encounter_db_v1.go` on `EncounterId`, `billing/billing_invoice_v2.go` on `InvoiceId`, `clinical/clinical_observation_v1.go` on `ObservationCode`). Cross-domain semantic references (`patientId: patient.PatientId` in clinical/billing) get spelled `PatientPatientId` - the whole dotted reference is pascalized in place - which is a second, equally-undefined name (`SchedulingPractitionerId` appears the same way).

**Root cause (read from source, not guessed):** `emitters/go.py::emit_go` (lines 16-24) iterates only `domain.models` (entities/aggregates/events/values) and `domain.projections`. It never iterates `domain.semantic_types`, and unlike `emitters/rust.py::_emit_semantic_type` there is no Go semantic-type emitter at all - nothing produces a `ThingId` struct or resolves the reference structurally to the underlying `uuid.UUID`. The `named`-kind shape for a semantic-typed field therefore falls through to the same `_pascalize(shape.ref)` fallback as finding #21, yielding a bare undefined name. (`cli/tests/test_emit_go.py` never uses a `semantic` declaration, so upstream has no test that would catch it.)

**Expected:** emit a semantic type for the Go target (e.g. a struct wrapping the underlying type, mirroring Rust's per-semantic-type artifact, or at minimum the underlying primitive inline with the `EMIT002` "cannot be represented without loss" warning) and resolve field references to it - the generated file must not reference an undefined name, and `@key` fields on real entities must compile.

**Showcase workaround:** none that avoids touching generated output (`UPSTREAM_POLICY.md` §1), same as findings #12/#13/#15/#16/#17/#18. `probes/go/` deliberately does not compile any artifact containing a semantic-typed field and documents why; `tests/integration/test_go_codegen.py` asserts the current failure explicitly. Until one of these two findings is fixed upstream, the Go target cannot compile any realistic Modelable workspace.

---

## 23. `compile --target grpc` emits one standalone service file per model into the same `modelable.<domain>.<version>.scalable` package - the full emitted graph cannot be compiled together

**Status:** Fixed in v1.8.0 via #365 (verified against the 1.8.0 regeneration: the full `generated/grpc/` output now compiles with `protoc`).

**Discovered:** Task 7.5 (Protobuf and gRPC compile probes), running the first real `protoc` over the entire `generated/grpc/` output. `protoc` was pinned via `scripts/install-protoc.sh` (see `.protoc-version`).

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  entity Alpha @ 1 (additive) {
    @key id: uuid
    name: string
  }

  entity Beta @ 1 (additive) {
    @key id: uuid
    name: string
  }
}
```

```bash
modelable compile . --target grpc --out ./dist
protoc -I ./dist -I "$(protoc --prefix)/include" \
  --descriptor_set_out=./probe.desc \
  ./dist/probe/Alpha.v1/Alpha.v1.grpc.proto \
  ./dist/probe/Beta.v1/Beta.v1.grpc.proto
```

**Observed:**

```text
probe/Beta.v1/Beta.v1.grpc.proto:8:10: "modelable.probe.v1.scalable.SchemaIdentity.model_id" is already defined in file "probe/Alpha.v1/Alpha.v1.grpc.proto".
probe/Beta.v1/Beta.v1.grpc.proto:9:10: "modelable.probe.v1.scalable.SchemaIdentity.model_name" is already defined in file "probe/Alpha.v1/Alpha.v1.grpc.proto".
...
```

Two entities in the same domain at the same version produce two `.grpc.proto` files that each redeclare the *entire* shared service surface - `SchemaIdentity`, `CommandEnvelope`, `CommandResultEnvelope`, `GetEntityRequest`, `ListEntitiesRequest`, `ListByIndexRequest`, `ReadResultEnvelope`, `ListResultEnvelope`, `IndexMetadata`, `ReadConsistency`, `CommandService`, `EntityReadService` - all in the same package `modelable.probe.v1.scalable`, so `protoc` rejects the second file as a redefinition. On this showcase's full `generated/grpc/` output (84 `.proto` files) the union fails with 98 `"..." is already defined` error lines, starting with `billing/InvoiceDb.v2/InvoiceDb.v2.grpc.proto` duplicating `billing/Invoice.v2/Invoice.v2.grpc.proto`. Any domain with more than one model or projection at a given version collides - billing.v2 (Invoice, InvoiceDb, InvoiceEvent, InvoiceReply, InvoiceRequest), clinical.v1 (Encounter + its Db/Event/Reply/Request/FhirView projections + Observation/ObservationFhirView/PatientFhirView), patient.v1/v2 (Patient + Db/Event/Reply/Request), scheduling.v1 (Appointment + Db/Event/Reply/Request/StatusChanged) - i.e. essentially every realistic domain.

The protobuf target is not affected, and neither is the per-file consumption mode: `protoc` compiles any single `.grpc.proto` file standalone (exit 0), the 44 non-`.grpc` schema `.proto` files in `generated/grpc/` compile together (exit 0), and `modelable compile --target grpc --descriptor-set` succeeds because it compiles each artifact individually - but the *union of the emitted graph* cannot be compiled, which is exactly what a downstream consumer does when they point `protoc` (or a code generator like `grpc_tools`/`buf`) at the whole generated directory.

**Root cause (read from source, not guessed):** `emitters/grpc.py::emit_grpc` writes one fully standalone service file per model *and* per projection, each via `_render_service_proto(package=f"{_package_name(domain, version)}.scalable")` (line 37) - the same package for every model at the same `domain`/`version`. `_render_service_proto` always emits the same boilerplate messages and services with no deduplication, no shared imported service module, and no per-model package distinction. There is nothing in the emitted output a consumer can use to combine multiple services of one domain version into a single deployable `.proto` set: the definitions simply collide. Nothing upstream checks for this: `cli/tests/test_emit_grpc.py` (if present) asserts on single-file text substrings only, and `--descriptor-set`'s per-file compilation sidesteps the collision rather than exposing it.

**Expected:** either emit the shared envelope/service surface once per `modelable.<domain>.<version>.scalable` package (e.g. a single shared service `.proto` file imported by per-model files that only add their own service/entity wiring), or give each model its own distinct package - either way, the full emitted graph for a realistic domain must compile with `protoc` in one invocation.

**Showcase workaround:** `tests/integration/test_protobuf_codegen.py` (Task 7.5) compiles the full protobuf graph, the gRPC schema `.proto` set, and each gRPC service file individually (the documented per-service mode `--descriptor-set` also uses), and asserts the full-graph failure explicitly so it flips when the emitter is fixed. Until #23 is fixed upstream, a consumer cannot compile an entire `generated/grpc/` tree in one `protoc` invocation.

## 24. `compile --target sql-postgres` emits bare secondary-index names that collide across tables in the shared schema - the full graph cannot be applied as-is

**Status:** Fixed in v1.8.0 via #365 (verified against the 1.8.0 regeneration: index names are now table-prefixed, e.g. `patient_db_by_name`/`appointment_db_by_status`, so the full DDL graph applies with every declared index present; the `#24` flip assertion was updated to the new names).

**Discovered:** Task 8.1 (PostgreSQL schema application), applying every file in `generated/sql-postgres/` to a real PostgreSQL (docker-compose.yml, `postgres:17-alpine`) in sorted filename order and then verifying the resulting schema. The DDL applies cleanly — every statement succeeds — but the resulting database is missing most of the generated secondary indexes.

**Reproduction:**

```mdl
domain probe {
  owner: "test"

  entity Patient @ 1 (additive) {
    @key id: uuid
    legalName: string
    dateOfBirth: date
  }

  entity Practitioner @ 1 (additive) {
    @key id: uuid
    legalName: string
    dateOfBirth: date
  }

  index Patient @ 1 {
    primary id
    secondary byName {
      key: [legalName]
      sort: [dateOfBirth]
    }
  }

  index Practitioner @ 1 {
    primary id
    secondary byName {
      key: [legalName]
      sort: [dateOfBirth]
    }
  }

  auto projections Patient @ 1 {
    db
  }

  auto projections Practitioner @ 1 {
    db
  }
}
```

```bash
modelable compile . --target sql-postgres --out ./dist
docker compose up -d postgres
uv run scripts/apply-postgres-ddl.py ./dist
psql -h 127.0.0.1 -p 5433 -U showcase -d showcase -c \
  "SELECT tablename, indexname FROM pg_indexes WHERE schemaname='public' ORDER BY tablename"
```

**Observed:**

```text
 tablename      | indexname
----------------+-----------
 patient_db     | by_name
 practitioner_db|          <- emitted "CREATE INDEX IF NOT EXISTS by_name ON practitioner_db" but the index is silently absent
```

Both `.sql` files emit `CREATE INDEX IF NOT EXISTS by_name ON <own_table> (...)` — with no table/domain prefix — and PostgreSQL scopes index names *per schema*, not per table. The first statement to run takes the name; every later `CREATE INDEX IF NOT EXISTS by_name` then finds an index with that name already in the schema and silently no-ops. On this showcase's full `generated/sql-postgres/` output the same collision strips nearly every secondary index: the emitted set declares `by_name` on six tables (`patient_db`, `patient_event`, `patient_reply`, `patient_request`, `patient_fhir_view`, `patient_summary`), `by_patient`/`by_status` on five invoice-family tables plus `outstanding_invoices`, and `by_patient_day`/`by_practitioner_day`/`by_status` on the four scheduling tables — but the applied database ends up with `by_name` only on `patient_fhir_view`, `by_patient`/`by_status` only on `invoice_db`, `by_practitioner_day` only on `daily_schedule`, and `by_patient_day` only on `appointment_db` (i.e. the survivors are exactly the lexicographically-first applicant of each name). `patient_db`, the showcase's primary persistence table, ends up with *no* index at all. Because the collision is masked by `IF NOT EXISTS`, nothing reports it: applying the whole emitted graph looks successful and silently produces a schema that does not match what the DDL declares.

**Root cause (read from source, not guessed):** `emitters/sql.py::_emit_secondary_index_ddl` renders `CREATE {UNIQUE }INDEX IF NOT EXISTS {index_name} ON {table_name} (...)` where `index_name = _snake_case(secondary.name)` (line 207) — the bare declared index name with no table or domain prefix, identical across every projection of the declaring model and across any other model/domain that declares the same name. The `IF NOT EXISTS` keyword (added so a single file can be re-applied) is precisely what turns the cross-table collision into a silent skip instead of a hard error, so the defect is invisible in any per-file test. Nothing upstream checks this: `cli/tests/test_emit_sql.py` asserts on single-file text substrings only and never applies a whole target's output to a real database.

**Expected:** make the emitted index names unique across the schema — e.g. prefix them with the table name (`patient_db_by_name`) — or drop the explicit name and let PostgreSQL derive one from table+columns, or emit per-domain schemas. Any of these makes the full generated graph applyable in one pass with every declared index present.

**Showcase workaround:** `tests/integration/test_postgres_generated_schema.py` (Task 8.1) applies the full generated set with `scripts/apply-postgres-ddl.py` (deterministic sorted filename order, statements executed verbatim), verifies every generated table, the representative patient/appointment/invoice columns and SQL types, and synthetic-row insert/read-back round-trips — all through psycopg — and pins the exact applied index reality (which index names survive the collision on `patient_db`/`appointment_db`/`invoice_db`) as explicit assertions that flip when the emitter is fixed. Until #24 is fixed upstream, a consumer cannot apply an entire `generated/sql-postgres/` tree and end up with the schema its DDL declares.

## 25. `compile --target sql-clickhouse` emits optional array fields as `Nullable(Array(T))` — an illegal ClickHouse type, so the full generated graph cannot be applied at all

**Status:** Fixed in v1.8.0 via #365 (verified against the 1.8.0 regeneration: optional array fields are now emitted as bare `Array(T)`, so the full clickhouse set applies; the `#25` flip assertion was updated accordingly).

**Discovered:** Task 8.2 (ClickHouse schema application), while running `scripts/apply-clickhouse-ddl.py` over the whole `generated/sql-clickhouse/` output against a real ClickHouse (the pinned `clickhouse/clickhouse-server:24.8-alpine` from the showcase's compose file).

**Reproduction:**

```mdl
domain patient @ 1 (additive) {
  @key id: uuid
  alternatePhoneNumbers?: array<string>
}
```

```bash
modelable compile . --target sql-clickhouse --out ./dist
docker compose up -d clickhouse
uv run scripts/apply-clickhouse-ddl.py ./dist
```

**Observed:**

```text
error: failed to apply dist: DB::Exception: Nested type Array(String) cannot be inside Nullable type.
(ILLEGAL_TYPE_OF_ARGUMENT) (version 24.8.14.39 (official build))
```

The generated column is `alternate_phone_numbers Nullable(Array(String))`, and ClickHouse rejects `Nullable` around any `Array` (arrays are not nullable in ClickHouse). On this showcase's full `generated/sql-clickhouse/` output, six tables declare an optional array field — `patient.PatientDb.v2`, `patient.PatientEvent.v2`, `patient.PatientReply.v2`, `patient.PatientRequest.v2`, `clinical.EncounterDb.v1`, `clinical.EncounterEvent.v1`, `clinical.EncounterReply.v1`, `clinical.EncounterRequest.v1` (`alternate_phone_numbers` / `diagnoses`) — so the sorted apply aborts at the first one (`clinical.EncounterDb.v1`): nothing after it is applied at all, and the failure is a hard server-side error, not a silent skip. Every domain with an optional array field cannot be applied. The postgres target is unaffected — it renders the same fields as `TEXT[]`/`VARCHAR(16)[]`, which PostgreSQL accepts.

**Root cause (read from source, not guessed):** `emitters/sql.py::_ch_col_type` (line 387–389) renders any optional field as `f"Nullable({base})"` where `base` comes from `_ch_base_type`; when the field is an array, `_ch_base_type` returns `Array(<element>)` (line 373–375), so the optional branch produces `Nullable(Array(<element>))`. `Nullable` cannot wrap `Array` in ClickHouse (`ILLEGAL_TYPE_OF_ARGUMENT`), and because the wrapped form is not rejected at compile time, `modelable compile --target sql-clickhouse` succeeds while emitting DDL the server refuses. Nothing upstream checks this: `cli/tests/test_emit_sql.py` asserts on emitted text only and never applies a clickhouse target's output to a server.

**Expected:** optional array fields must be emitted as a nullable-safe ClickHouse form — e.g. bare `Array(T)` plus `[]` defaulting in the app layer, or `Array(Nullable(T))` only for element-level nullability — so the full generated graph applies in one pass.

**Showcase workaround:** `tests/integration/test_clickhouse_generated_schema.py` (Task 8.2) applies the six `reporting.*` tables (the representative reporting surface — no array columns, so they apply cleanly) with `scripts/apply-clickhouse-ddl.py`, verifies deterministic sorted application is idempotent, verifies the reporting tables exist with exact columns/types, inserts synthetic aggregate/report rows and queries them back through clickhouse-connect, and pins the #25 reality as an explicit flip test: applying the *full* generated set must currently fail with the `Nullable(Array(...))`/`ILLEGAL_TYPE_OF_ARGUMENT` error. It also asserts no `CREATE INDEX` anywhere in the generated clickhouse DDL (that capability is deferred upstream). Until #25 is fixed upstream, a consumer cannot apply an entire `generated/sql-clickhouse/` tree.

## 26. `compile --target rust` emits `status: src.status.into()` between projection status enums without generating the `From` impl - billing-core still does not compile

**Status:** Fixed upstream, shipped in **v1.9.0** (verified: `cargo check` on billing-core no longer errors on the missing `From` impl), and fully usable from **v1.9.2** once the #35 and #36 regressions in the same emitter line were also fixed. New finding discovered while reviewing the v1.8.0 regeneration (the `.into()` was previously unreachable because billing-core already failed to compile for #14; with #14 fixed, this is now the *first* hard error in `cargo check` on billing-core).

**Discovered:** Task 9.4 (generated API contracts), re-running `cargo check` on `generated/rust/billing-core` against the v1.8.0 output after #14 was verified fixed.

**Reproduction:**

```bash
cargo check --manifest-path generated/rust/billing-core/Cargo.toml
```

**Observed:**

```text
error[E0277]: the trait bound `ReportingOutstandingInvoicesV1Status: From<BillingInvoiceV2Status>` is not satisfied
 --> src/reporting/reporting_outstanding_invoices_v1.rs:64:17
  |
64 |             status: src.status.into(),
```

`generated/rust/billing-core/src/reporting/reporting_outstanding_invoices_v1.rs` implements `From<BillingInvoiceV2> for ReportingOutstandingInvoicesV1` and calls `src.status.into()` (line 64), but no `impl From<BillingInvoiceV2Status> for ReportingOutstandingInvoicesV1Status` is emitted. The two enums are structurally identical — both `BillingInvoiceV2Status` and `ReportingOutstandingInvoicesV1Status` declare the same five variants `Draft`/`Issued`/`Paid`/`Overdue`/`Void` with identical serde renames — so the missing impl is purely a codegen omission, not a semantic mismatch. Every other `.into()` on the same line block (UUIDs, decimals, timestamps, value objects) has a corresponding emitted `From`; only the projection status enum is skipped. `reporting-core` is unaffected (it does not convert between status enums), and `clinical-core` compiles cleanly, so billing-core is the only remaining failing crate.

**Root cause (read from source, not guessed):** `emitters/rust.py`'s projection `From` generation handles field-level conversion for named types and value objects but has no branch for converting one domain/status enum into another; the status field is emitted as a plain `.into()` with no accompanying `impl From`. The upstream Rust test suite (`cli/tests/` for the rust target) does not `cargo check` a projection whose source and target status enums differ, so nothing upstream exercises this path.

**Expected:** either emit `impl From<BillingInvoiceV2Status> for ReportingOutstandingInvoicesV1Status` alongside the projection's `From<BillingInvoiceV2> for ReportingOutstandingInvoicesV1`, or emit the field assignment without `.into()` (the enums are structurally identical, so a direct assignment compiles).

**Showcase workaround:** `tests/integration/test_rust_codegen.py`'s billing flip test pins the exact #26 error text against the current v1.8.0 output. Until #26 is fixed upstream, `generated/rust/billing-core` does not compile, so Task 9.4's generated billing contracts cannot be built — the API layer must hand-write its invoice status mapping until then.

## 27. `compile --target sql-postgres` emits `FOREIGN KEY (...)` referencing the model name, not the bound table name - the full graph cannot be applied

**Status:** Fixed in v1.9.4. The SQL emitter now
uses the referenced `*Db` projection's default table name when no explicit
binding is present, while preserving explicit binding overrides.

**Discovered:** Task 8.1 follow-up, after resetting the showcase PostgreSQL schema (`DROP SCHEMA public CASCADE; CREATE SCHEMA public`) and re-applying the full regenerated `generated/sql-postgres/` set.

**Reproduction:**

```bash
modelable compile . --target sql-postgres --out ./dist   # (or regenerate via scripts/generate-all.py)
uv run scripts/apply-postgres-ddl.py ./dist
```

**Observed:**

```text
psycopg.errors.UndefinedTable: relation "encounter" does not exist
```

The emitted DDL now includes foreign keys (a v1.8.0 feature), but every one references the *model* name rather than the *bound* table name:

- `generated/sql-postgres/billing.InvoiceDb.v2.sql`: `FOREIGN KEY (encounter_id) REFERENCES encounter (encounter_id)` — the target table is `encounter_db`.
- `generated/sql-postgres/scheduling.AppointmentDb.v1.sql`: `FOREIGN KEY (patient_id) REFERENCES patient (patient_id)` — the target table is `patient_db`.
- `generated/sql-postgres/clinical.EncounterDb.v1.sql`: `FOREIGN KEY (appointment_id) REFERENCES appointment (appointment_id)` — the target table is `appointment_db`.

There is no `encounter`, `patient`, or `appointment` table in the generated set — the tables are `encounter_db`, `patient_db`, `appointment_db` (and the Event/Reply/Request projections). When the FK references are emitted in the same file that creates the target's `_db` table, PostgreSQL happens to already have created it if the file sorts earlier; but when the FK target model's table is created *later* in sorted order (or is only ever created as part of a graph that includes the source file first), the reference is unresolvable at the point of the first create. On this showcase's sorted apply, `encounter` never exists as a relation at all, so the very first FK statement aborts the whole apply. The error is a hard server-side failure mid-apply — nothing is applied after it — exactly the loud-crash class of #25 rather than #24's silent skip. Because `patient`/`encounter`/`appointment` are also the names of other *models* in this showcase, the emitted FK silently makes the DDL depend on nonexistent relations and cannot even be fixed by reordering files.

**Root cause (read from source, not guessed):** the new FK emission in `emitters/sql.py` renders the referenced table from the referenced model's *name* (e.g. `encounter`), not from the model's *binding* (`encounter_db` as declared in the workspace's `table:` bindings). The single-table apply tests in `cli/tests/test_emit_sql.py` assert on text only and never apply the FK output to a real server, so the wrong identifier is never caught.

**Expected:** the FK `REFERENCES` clause must use the same bound table name the `CREATE TABLE` uses (`REFERENCES encounter_db (encounter_id)` etc.), so the full graph applies in one pass with all FKs intact.

**Showcase verification:** `tests/integration/test_postgres_generated_schema.py`
now applies the complete generated tree and asserts the FK clauses reference
`encounter_db`, `patient_db`, and `appointment_db`.

## 28. `compile --target csharp` never imports or qualifies types from another domain - cross-domain field references are still compile errors

**Status:** Fixed via #37 (reference-scoped cross-domain imports + inline cross-domain semantic resolution; upstream PR pending). This was the residual half of #15/#16 after the v1.8.0 (#365) fix: named-type and semantic-type references now resolve *within* the declaring domain, but references into another domain's namespace were emitted bare with no `using` import, so the full generated set failed `dotnet build`. The #37 fix adds reference-scoped `using` directives and inlines cross-domain semantics, so the full `generated/csharp/` set now builds.

**Discovered:** Task 7.2 follow-up (C# probe), rebuilding the full `generated/csharp/` set against v1.8.0 after #15/#16 were verified fixed for same-domain references.

**Reproduction:**

```bash
dotnet build probes/csharp/ModelableShowcase.Probe.csproj
```

**Observed:**

```text
error CS0246: The type or namespace name 'PatientPatientId' could not be found (are you missing a using directive or an assembly reference?)
```

`generated/csharp/billing.Invoice.v2.cs` declares `namespace Modelable.Billing;` and uses `public required PatientPatientId PatientId { get; init; }` (line 10) — but `PatientPatientId` is a semantic type in the `patient` domain, emitted as `Modelable.Patient.PatientPatientId`, and the file emits no `using Modelable.Patient;`. The same class of error hits `SchedulingPractitionerId` (used by `clinical.Encounter*`), `SchedulingTimeRangeV0` (used by `scheduling.Appointment*` and `reporting.DailySchedule.v1`), and `PatientContactDetailsV0` (used by `clinical.PatientFhirView.v1` and `reporting.PatientClinicalSummary.v1`). The records themselves are emitted (e.g. `patient.ContactDetails.v0.cs`, `scheduling.TimeRange.v0.cs`); only the cross-namespace reference is unresolved. Same-domain references (e.g. `BillingInvoiceLineV0` inside `billing.*`) are fixed by #365 and compile.

**Root cause (read from source, not guessed):** `emitters/csharp.py` resolves named-type/semantic-type references by emitting the bare type name, and only emits `using` directives for types in the *current* domain's namespace; it never emits a `using` (or fully-qualified name) for a type declared in another domain. The upstream C# test fixture is a single domain, so cross-domain resolution is never exercised.

**Expected:** when a field's type resolves to a declaration in another domain, either emit `using Modelable.<ThatDomain>;` at the top of the file or emit the fully-qualified `Modelable.<ThatDomain>.<TypeName>` in the field position.

**Showcase workaround:** `tests/integration/test_csharp_codegen.py`'s full-set flip test pins the exact #28 error against the v1.8.0 output (asserting the build of the full generated set fails with one of the cross-domain CS0246 errors above). Until #28 is fixed upstream, the full `generated/csharp/` set does not compile; the C# probe builds only the same-domain surface.

## 29. `compile --target java` never imports or qualifies types from another domain - cross-domain field references are still compile errors

**Status:** Fixed via #37 (reference-scoped cross-domain imports + inline cross-domain semantic resolution; upstream PR pending). The Java analogue of #28 — the residual half of #17/#18 after the v1.8.0 (#365) fix. The full `generated/java/` set now compiles.

**Discovered:** Task 7.3 follow-up (Java probe), rebuilding the full `generated/java/` set against v1.8.0.

**Reproduction:**

```bash
mvn -q -f probes/java/pom.xml compile
```

**Observed:**

```text
[ERROR] .../billing/InvoiceV2.java:[..] error: cannot find symbol
[ERROR]   symbol:   class PatientPatientId
```

`generated/java/billing/InvoiceV2.java` declares `package modelable.billing;` and uses `public PatientPatientId patientId;` with no import for `modelable.patient.PatientPatientId`. The Java emitter never emits cross-package `import` statements for referenced types from another domain, so every cross-domain field reference is a `cannot find symbol` error. Same-domain references (e.g. `InvoiceLineV0` inside `billing.*`) are fixed by #365 and compile.

**Root cause (read from source, not guessed):** the same single-domain assumption as #28, in `emitters/java.py` — references to types declared in another domain are emitted bare with no `import modelable.<domain>.<Type>;`.

**Expected:** emit the cross-package `import` for referenced types declared in another domain (or fully-qualify the type name in the field position).

**Showcase workaround:** `tests/integration/test_java_codegen.py`'s full-set flip test pins the exact #29 error against the v1.8.0 output. Until #29 is fixed upstream, the full `generated/java/` set does not compile; the Java probe builds only the same-domain surface.

## 30. `compile --target python` never imports referenced types from other modules - annotations still do not resolve cross-module

**Status:** Fix verified in [ktjn/modelable#418](https://github.com/ktjn/modelable/pull/418) (draft). Verified by installing that exact branch (`git+https://github.com/ktjn/modelable@agent/fix-final-upstream-gaps#subdirectory=cli`), recompiling this showcase's real `model/` to `python`, and re-running this finding's own reproduction plus the same-domain variant: `typing.get_type_hints(ClinicalEncounterV1)` and `typing.get_type_hints(PatientPatientDbV2)` both now resolve cleanly, with no `NameError`, for both the originally-reported cross-domain case and the same-domain case (`patient.Patient.contact`/`.address` importing `PatientContactDetailsV0`/`PatientAddressV0` from sibling same-domain modules). PR #418's diff to `_shape_base_annotation` in `emitters/python.py` changes the import-emission guard from `declaring_domain != current_domain` (which incorrectly skipped same-domain sibling-module imports) to `named_name != owner_type` (which correctly imports any type not being self-referenced, regardless of domain) - a one-line, root-cause-targeted fix, not a workaround.

**Original discovery** (superseded by the #418 verification above, kept for history): re-verified against v1.9.4 (Task 16.1, CI workflow first run - `probes/python`'s test suite was never actually executed end-to-end in this showcase before this task's CI added the first real invocation): **not fixed, and broader than originally scoped.** #37 did fix the *semantic-typed* half of this - a cross-domain semantic-typed field (e.g. `clinical.Encounter.patientId`, semantically `patient.PatientId`) is now emitted as its bare underlying primitive (`patientId: UUID`) rather than an unimported semantic-type name, sidestepping the original `NameError` entirely (a representation change, not an import fix). But the *value-typed* half is unchanged, and - contrary to #19's "same-module references now resolve" framing - this reproduces for same-domain references too, not just cross-domain: `generated/python/clinical/clinical_encounter_v1.py` (domain `clinical`) declares `diagnoses: Optional[list[ClinicalDiagnosisV0]]`, and `ClinicalDiagnosisV0` is defined in the *same* domain directory (`clinical_diagnosis_v0.py`) - yet `clinical_encounter_v1.py` has no `from .clinical_diagnosis_v0 import ClinicalDiagnosisV0` (or any import at all beyond stdlib). `typing.get_type_hints(ClinicalEncounterV1)` still raises `NameError: name 'ClinicalDiagnosisV0' is not defined`. Same for `patient.Patient.contact`/`patient.Patient.address` referencing `PatientContactDetailsV0`/`PatientAddressV0` within the same `patient` domain.

**Discovered:** Task 7.4 follow-up (Python probe), re-running annotation resolution against the v1.8.0 output.

**Reproduction:**

```python
import typing
from generated.python.clinical.clinical_encounter_v1 import ClinicalEncounterV1
typing.get_type_hints(ClinicalEncounterV1)
```

**Observed:**

```text
NameError: name 'PatientPatientId' is not defined
```

`generated/python/clinical/clinical_encounter_v1.py` starts with `from __future__ import annotations` and only stdlib imports (`dataclasses`, `datetime`, `decimal`, `typing`, `uuid`), then declares `patientId: PatientPatientId` and `practitionerId: SchedulingPractitionerId` (lines 12–13) with no import from `generated.python.patient.patient_patient_id` or `generated.python.scheduling.scheduling_practitioner_id`. Because of the lazy `__future__` string annotations, the module imports and dataclasses instantiate fine — the breakage is latent exactly like pre-fix #19/#20 — and only surfaces when annotations are resolved (`typing.get_type_hints`) or consumed by typed tooling. The referenced types are emitted (e.g. `generated/python/patient/patient_contact_details_v0.py`), and same-module references (e.g. `ClinicalDiagnosisV0` within `clinical`) are fixed by #365 and resolve.

**Root cause (read from source, not guessed):** `emitters/python.py` emits imports for the current domain's own type declarations but never emits a sibling `import` for a type declared in another domain's module.

**Expected:** emit `from <sibling module path> import <TypeName>` for each referenced type declared in another domain's module, so `typing.get_type_hints` resolves the full graph.

**Showcase workaround:** `tests/integration/test_python_codegen.py`'s full-set flip test still pins the exact #30 error against the pinned `1.9.4` output (annotation resolution over a cross-module class must currently raise `NameError`), since the showcase has not re-pinned to #418's unreleased branch. Will need flipping to expect resolution once a release including #418 is adopted.

## 31. `compile --target go` never imports or qualifies types from another package - cross-domain field references are still compile errors

**Status:** Fixed via #37 (reference-scoped cross-package imports + emitted `go.mod` + inline cross-domain semantic resolution; upstream PR pending). The Go residual of #21/#22 after the v1.8.0 (#365) fix: same-package references now resolve, but a package that references a type declared in another domain's package emitted the bare name with no import. The #37 fix adds reference-scoped package imports, an emitted `go.mod` (module `modelable/generated`), and inlines cross-domain semantics, so the full `generated/go/` module now builds.

**Discovered:** Task 7.4 follow-up (Go probe), re-running `go build` over the full `generated/go/` set against v1.8.0.

**Reproduction:**

```bash
go build ./...
```

in the generated Go module.

**Observed:**

```text
undefined: PatientPatientId
```

`generated/go/billing/` files use `PatientPatientId` (for `Invoice.PatientId`) with no `import` of the `patient` package; `generated/go/clinical/` uses `PatientPatientId` and `SchedulingPractitionerId`; `generated/go/reporting/` uses `PatientPatientId` and `SchedulingTimeRangeV0` (from `scheduling`). None of these cross-package references has a corresponding Go import, so the full module does not build. Same-package references (e.g. `InvoiceLineV0` within `billing`) are fixed by #365 and build.

**Root cause (read from source, not guessed):** the same single-domain assumption as #28/#29, in `emitters/go.py` — references to types declared in another domain's package are emitted bare with no import of that package (and no package-qualified name).

**Expected:** emit the `import` of the referenced type's package (or qualify the type with its package name) when the declaration lives in another domain.

**Showcase workaround:** `tests/integration/test_go_codegen.py`'s full-set flip test pins the exact #31 error against the v1.8.0 output. Until #31 is fixed upstream, the full `generated/go/` module does not build; the Go probe builds only the same-package surface.

## 32. `modelable generate --from json-schema` emits the raw `$ref` JSON Pointer (`#/$defs/<Type>`) as a field type - imported schemas fail to parse

**Status:** Fixed (landed in the pinned release — verified on the 1.9.2 regeneration: `$ref`-typed fields now import as semantic types and the round-trip validates cleanly). Discovered while re-running the `test_cli_surface.py` round-trip tests against the v1.8.0 pin (the first time the json-schema importer is exercised end-to-end on this showcase's output).

**Discovered:** Task 4.3/CLI-surface follow-up, running `modelable generate --from json-schema` over this showcase's own generated `generated/json-schema/` artifacts.

**Reproduction:**

```bash
modelable generate --from json-schema --input generated/json-schema/billing.Invoice.v2.json --out /tmp/roundtrip
modelable validate /tmp/roundtrip
```

**Observed:**

```text
ERROR No terminal matches '#' in the current parser context, at line 5 col 49
```

The importer maps `$ref` fields to a bare type token. `generated/json-schema/billing.Invoice.v2.json` declares `"patientId": { "$ref": "#/$defs/Patient.PatientId" }`, and the round-trip emits `patientId: #/$defs/Patient.PatientId` — the literal JSON Pointer as a Modelable field type, which the Modelable parser rejects (`#` has no terminal match). The pointer-to-`$defs` mapping never resolves to the *type name* (`Patient.PatientId`). The generated json-schema artifacts themselves are self-consistent (all `$defs` present, no dangling refs — 32 files, 0 dangling), so the defect is entirely in the importer. Fields with primitive types round-trip fine; only `$ref`-typed fields (semantic types and named types) break.

**Root cause (read from source, not guessed):** `cli/generate/` (the `--from json-schema` importer) emits the raw `$ref` string as the field type instead of resolving the fragment against the artifact's `$defs` and emitting the declaration's `title`/`x-modelable` named type. The upstream test for this importer covers only primitive-typed schemas.

**Expected:** resolve `#/$defs/<X>` against the document's `$defs` and emit the referenced type's stable name (e.g. `patientId: Patient.PatientId`), emitting the referenced `$defs` declarations into the output workspace where needed.

**Showcase workaround:** `tests/integration/test_cli_surface.py::test_generate_from_json_schema_preserves_governance_metadata` pins the #32 reality: round-tripping a schema with a `$ref`-typed field must currently fail with the parser error above, and the test verifies that primitive-only schemas still round-trip. Until #32 is fixed upstream, `generate --from json-schema` cannot import any schema that references a semantic/named type.

## 33. `modelable generate --from odcs` imports semantic/value-type references without their declarations - imported models fail validation

**Status:** Fixed (landed in the pinned release — verified on the 1.9.2 regeneration: the referenced `semantic`/`value` types are now declared on import and the round-trip validates cleanly). Discovered alongside #32 while re-running `test_cli_surface.py` round-trips against the v1.8.0 pin.

**Discovered:** Task 4.3/CLI-surface follow-up, running `modelable generate --from odcs` over this showcase's own generated `generated/odcs/` artifacts.

**Reproduction:**

```bash
modelable generate --from odcs --input generated/odcs/billing.Invoice.v2.odcs.yaml --out /tmp/roundtrip
modelable validate /tmp/roundtrip
```

**Observed:**

```text
unknown semantic type 'PatientId'
```

`generated/odcs/billing.Invoice.v2.odcs.yaml` encodes the field as `logicalType: object` with `customProperties` `modelableType: patient.PatientId` / `modelableNamedType: patient.PatientId`. The importer turns that into `patientId: PatientId` (dropping the `patient.` domain qualifier) and imports the reference without any accompanying `semantic` declaration for `PatientId` (or the value type), so `modelable validate` fails: the model references a semantic type that is never declared. The same applies to value-type references like `InvoiceLine` (emitted as `lines: array<InvoiceLine>` with no `value InvoiceLine` declaration in the output). The generated ODCS artifacts themselves are well-formed (their `customProperties` correctly record the source types), so the defect is in the importer.

**Root cause (read from source, not guessed):** `cli/generate/` (the `--from odcs` importer) maps `modelableType`/`modelableNamedType` to bare type tokens but does not carry the domain-qualified name through, and never synthesizes the `semantic`/`value` declarations the referenced types need. The upstream test for this importer covers only primitive-typed contracts.

**Expected:** import `modelableType`/`modelableNamedType` values with their domain qualification (e.g. `patientId: patient.PatientId`), and emit the referenced `semantic`/`value` declarations into the output workspace (or validate against a workspace that already declares them).

**Showcase workaround:** `tests/integration/test_cli_surface.py::test_generate_from_odcs_preserves_metadata_and_exact_type_hints` pins the #33 reality: round-tripping a contract with a semantic/value-typed field must currently fail with `unknown semantic type ...`, and the test verifies that primitive-only contracts still round-trip. Until #33 is fixed upstream, `generate --from odcs` cannot import any contract that references a semantic or named type.

## 34. `compile --target rust` marks every `Option` field `#[serde(skip_serializing_if = "Option::is_none")]` without `#[serde(default)]` - a serialized projection cannot be deserialized back when an optional is `None`

**Status:** Fixed upstream, shipped in **v1.9.0** (the emitter now writes `#[serde(default)]`), and fully usable from **v1.9.1** once the regression it introduced (finding **#35**) was fixed. Verified on 1.9.2: every `Option` field now carries exactly one `#[serde(default)]` alongside `skip_serializing_if`.

**Discovered:** Task 9.2/9.3 follow-up, when the API's created-reply JSON (which omits `None` optionals) was round-tripped through the generated reply type and serde rejected it.

**Reproduction:**

```bash
cd apps/api && cargo test --test scheduling_api appointment_reply_json_shape_matches_generated_types
```

**Observed:**

```text
created reply must deserialize into the generated SchedulingAppointmentReplyV1:
Error("missing field `buffer_duration`", line: 0, column: 0)
```

The rust emitter renders every optional field as `#[serde(skip_serializing_if = "Option::is_none")]` (e.g. `generated/rust/clinic-core/src/scheduling/scheduling_appointment_reply_v1.rs` and `.../patient_patient_reply_v2.rs`), so serialization omits `None` fields. But the same field is never annotated `#[serde(default)]`, so serde's deserializer demands the key be present. A projection with a `None` optional therefore serializes to a document that its own type cannot deserialize — the JSON round-trip is not idempotent. Required fields (`appointment_id`, `scheduled_date`, ...) and `Some` optionals all round-trip; only a `None` optional breaks it.

**Root cause (read from source, not guessed):** `emitters/rust.py` writes `skip_serializing_if` for every `Option` field but never writes `default`. The upstream Rust codegen tests only assert serialization output, never a serialize-then-deserialize round-trip, so the asymmetry is not caught.

**Expected:** emit `#[serde(default)]` alongside `skip_serializing_if` on every `Option` field (as the emitter already does for value-type fields like `PatientContactDetailsV0.email`), so a serialized projection deserializes back into the same type regardless of which optionals are `None`.

**Showcase workaround:** the showcase API persists and returns the generated reply types, whose own `skip_serializing_if` is authoritative, so the HTTP responses are correct and complete (omitted optionals are semantically `null`). What cannot happen is deserializing that same JSON back into the generated type. `apps/api/tests/scheduling_api.rs::appointment_reply_json_shape_matches_generated_types` pins the reality: it asserts the created reply's field set, and to exercise the generated type's deserializer it uses a hand-built full JSON with every optional present, rather than the API's own omitted-optional output. Until #34 is fixed upstream, any Rust consumer that serializes a projection with a `None` optional cannot feed that document back into the generated type.

## 35. `compile --target rust` emits `#[serde(default)]` twice on every optional field that already carried it - a hard serde derive error, so all generated Rust crates fail to compile

**Status:** Fixed upstream in **v1.9.1** via [ktjn/modelable#387](https://github.com/ktjn/modelable/pull/387) ("fix: deduplicate Rust serde defaults"). Regression introduced by the v1.9.0 fix for #34: adding `#[serde(default)]` to every `Option` field also re-adds it to the optional fields that already had one (the value-type projection files), producing a duplicate-attribute `error: duplicate serde attribute 'default'`. Because the affected value-type projection files are compiled as part of every generated crate, **all three** of `clinic-core`, `clinical-core`, and `billing-core` fail to compile on 1.9.0.

**Discovered:** Task 9.4 (generated API contracts), running `cargo check` on `generated/rust/*` after re-pinning from 1.8.0 to 1.9.0 to adopt the #26 fix.

**Reproduction:**

```bash
modelable compile . --target rust --out ./dist
cargo check --manifest-path dist/clinic-core/Cargo.toml
```

**Observed:**

```text
error: duplicate serde attribute `default`
 --> src/patient/patient_contact_details_v0.rs:7:13
  |
7 |     #[serde(default)]
  |             ^^^^^^^
```

The 1.9.0 emitter renders every `Option` field as:

```rust
#[serde(default)]
#[serde(skip_serializing_if = "Option::is_none")]
#[serde(default)]
pub preferred_name: Option<String>,
```

i.e. `#[serde(default)]` is written both as the #34 standalone addition *and* as the existing attribute already paired with `skip_serializing_if`. The duplicates occur only in the value-type projection files (`patient_contact_details_v0.rs`, `patient_patient_v1.rs`, `patient_patient_v2.rs`, `scheduling_appointment_v1.rs`, `scheduling_appointment_status_changed_v1.rs`, `clinical_encounter_v1.rs`, etc.) — exactly the files whose optional fields already carried `#[serde(default)]` before #34 — but those files are compiled by every downstream crate, so the entire Rust target is unusable on 1.9.0. (Required-field files like `clinical_encounter_db_v1.rs` get a single `default` and are fine; only files where `skip_serializing_if` was already paired with `default` double up.)

**Root cause (read from source, not guessed):** `emitters/rust.py`'s #34 change writes `#[serde(default)]` before every `Option` field without checking whether the field already had a `default` attribute (value-type fields, and the optional-with-`skip_serializing_if` path, already emitted one). The upstream Rust codegen tests assert single-field serialization substrings, not a full `cargo check` of a generated crate, so the doubled attribute is not caught.

**Expected:** emit `#[serde(default)]` exactly once per `Option` field — the standalone addition should not be written when the field already carries a `default` attribute (or the emitter should emit a single combined `#[serde(default, skip_serializing_if = "Option::is_none")]`), and an upstream `cargo check` over the generated crate should be part of the Rust emitter's gates.

**Showcase workaround:** none that avoids touching generated output (`UPSTREAM_POLICY.md` §1). The showcase remains pinned to **1.8.0** (`.modelable-version`) until #35 is fixed upstream and released, since 1.9.0's generated Rust does not compile at all. Task 9.4's generated-clinical/billing contracts cannot be built until then.

## 36. `compile --target rust` emits cross-domain status-enum `From` impls importing via `super::{domain}::` - invalid for sibling top-level modules in the same package crate, so billing-core fails to compile

**Status:** Fixed upstream in **v1.9.2** via [ktjn/modelable#389](https://github.com/ktjn/modelable/pull/389) ("fix: repair package-mode cross-domain Rust imports"). Regression introduced by the v1.9.0 fix for #26 (which first emitted cross-domain projection status-enum `From` impls): the appended `From` blocks import the source enum with `use super::{domain}::{module}`, but in package mode `billing` and `reporting` are sibling top-level modules of the same crate (`src/lib.rs` is `pub mod billing; pub mod reporting;`), so `super::reporting` from inside `src/billing/` resolves to `billing::reporting` (nonexistent). The normal named-type import path uses `_import_prefix` (correctly `crate::{domain}::`), but `_append_cross_enum_from_impls` hardcoded `super::` and was never told about package mode.

**Discovered:** Task 9.4 (generated API contracts), running `cargo check` on `generated/rust/billing-core` after re-pinning to 1.9.1 to adopt the #26/#35 fixes.

**Reproduction:**

```bash
modelable compile . --target rust --out ./dist
cargo check --manifest-path dist/billing-core/Cargo.toml
```

**Observed:**

```text
error[E0433]: cannot find `reporting` in `super`
 --> src/billing/billing_invoice_db_v2.rs:149:12
149 | use super::reporting::reporting_outstanding_invoices_v1::ReportingOutstandingInvoicesV1Status;
```

**Root cause (read from source, not guessed):** `emitters/rust.py::_append_cross_enum_from_impls` computed the source import path as `super::{domain_mod}::{module}` when the source and target domains differed, without consulting `package_for_domain`. In package mode the two domains live in the same crate as sibling top-level modules, so the correct path is `crate::{domain_mod}::{module}`. The existing upstream tests covered cross-domain enum `From` impls in flat mode only (where `super::` is correct) or in cross-package mode (where a different projection-From path is used), so package-mode same-crate cross-domain status enums were never `cargo check`ed.

**Expected:** `_append_cross_enum_from_impls` must use the same package-aware prefix as the normal import path (`_import_prefix`): same-domain `super::`, same-package-different-domain `crate::{domain}::`, cross-package `{crate}::{domain}::`. An upstream test should compile a same-package two-domain workspace with a cross-domain status-enum projection.

**Showcase workaround:** none that avoids touching generated output (`UPSTREAM_POLICY.md` §1). The showcase could not re-pin past 1.8.0 while 1.9.1's billing-core did not compile; the fix in #389 (shipped in v1.9.2) resolves it.
## 37. `compile --target go/java/python/csharp` 1.9.x cross-domain import feature over-imports all cross-domain types into every file and emits wrong/unresolvable import paths, and cross-domain semantic refs still emit a bogus `pascalized` named type - standalone packages and full-set builds break

**Status:** Fixed upstream in **v1.9.3** via [ktjn/modelable#391](https://github.com/ktjn/modelable/pull/391). Discovered while re-pinning the showcase from 1.8.0 to 1.9.2: the 1.9.x "cross-domain import" feature (commit `917de67`, "close showcase emitter and importer gaps") was applied across the go/java/python/csharp emitters with two defects, and never landed with tests that compile the output.

**Discovered:** Task 9.8/1.9.2 flip work, running the go/java/python/csharp codegen probes against the 1.9.2 regeneration.

**Reproduction (Go):**

```bash
modelable compile . --target go --out ./dist
cd ./dist && go build ./...
```

**Observed (BUG A — over-importing + wrong paths):**

```text
billing/billing_invoice_line_v0.go:5:5: package generated/audit is not in std
```

`billing_invoice_line_v0.go` is a pure value type (no cross-domain references) yet imports `generated/audit`, `generated/clinical`, `generated/patient`, `generated/scheduling`. The 1.9.x emitters blanket-import every cross-domain type/namespace into every file, regardless of whether the file references them, and use wrong module/package paths:

- **Go:** `_qualify_cross_domain_names` adds `import "generated/<domain>"` for every cross-domain name in every file, but the go target emits no `go.mod` and no module name, so `generated/<domain>` never resolves. It also mutates the shared `named_names` dict in place across artifacts, producing a double prefix (`scheduling.scheduling.SchedulingTimeRangeV0`).
- **Java:** `_header_lines` blanket-imports every model type of every other domain into every file.
- **Python:** `_header_lines` blanket-imports every model of every other domain into every file.
- **C#:** `_header_lines` blanket-`using` every other domain's namespace into every file.

**Observed (BUG B — cross-domain semantic refs):**

```text
undefined: PatientPatientId
```

A `semantic PatientId: uuid(7)` is emitted INLINE as its underlying primitive in its own domain, but a cross-domain reference `patient.PatientId` yields `shape.ref == "patient.PatientId"` (domain-qualified). The per-field `named` branch looks up the bare name in the bare-keyed `named_names`/`named_shapes` dicts, misses, and falls through to `_pascalize(shape.ref)` → a bogus `PatientPatientId` name that is never emitted. Same defect in all four emitters.

**Root cause (read from source, not guessed):** the per-emitter cross-domain code (go.py `_qualify_cross_domain_names`; java/python/csharp `_header_lines` blanket comprehensions) ignores per-file reference scope and (for Go) hardcodes a module path the target never defines. And `resolve_named_types` keys semantics only by bare name in `named_shapes`, so a qualified cross-domain ref never matches and falls to the pascalize fallback. No upstream test compiles a two-domain generated output, so neither defect was caught.

**Expected:** reference-scoped imports — only import/`using`/`from` a cross-domain type when a file actually references it, using correct per-language module/package paths (Go needs an emitted `go.mod`); and resolve cross-domain semantic refs to their inline underlying primitive exactly as same-domain refs do.

**Showcase workaround:** none that avoids touching generated output (`UPSTREAM_POLICY.md` 1). The fix is implemented upstream (emitters go.py/java.py/python.py/csharp.py + named_types.py, with tests) and, once merged/released, the full go/java/csharp/python sets build and the showcase flip tests were updated to assert that. #28/#29/#30/#31 were updated to Fixed in this release because the #37 fix (plus the #32/#33 importer fixes that shipped with the pin) closes the last of their residuals.

## 38. `compile --target openapi` emits a `$ref` to the bare source entity for `ref<Domain.Entity@N>` fields, but no component schema exists for a bare entity - the reference is unresolvable

**Status:** Fixed in v1.9.4. `ref<>` fields now use
the referenced model's key-field schema in OpenAPI, so the component graph is
resolvable.

**Discovered:** Task 9.6, independently validating `generated/openapi/openapi.json` with `openapi-spec-validator` (a parser separate from Modelable's own test suite, per `UPSTREAM_POLICY.md` §4.4/§5.3) after adding the showcase's first real `api {}` declarations.

**Reproduction:**

```bash
uv run python -c "
from openapi_spec_validator import validate
import json
validate(json.load(open('generated/openapi/openapi.json')))
"
```

**Observed:**

```text
referencing.exceptions.PointerToNowhere: '/components/schemas/patient.Patient.v2' does not exist
```

`scheduling.mdl` declares `Appointment.patientId: ref<patient.Patient@2>` (a cross-domain model reference, not a semantic-identifier reference like `practitionerId`). The openapi emitter renders every projection of `Appointment` (`AppointmentEvent`, `AppointmentReply`, `AppointmentRequest`) with `"patientId": {"$ref": "#/components/schemas/patient.Patient.v2"}` - but `components.schemas` only ever contains `patient.Patient{Db,Request,Reply,Event}.v2` (the auto-generated *projections*) and the value/semantic-type schemas (`PatientId`, `ContactDetails`, ...); the bare entity `patient.Patient.v2` itself is never emitted as a component. The same pattern repeats for every `ref<>` field in this showcase's model: `clinical.mdl`'s `Encounter.appointmentId: ref<scheduling.Appointment@1>` and `Observation.encounterId: ref<clinical.Encounter@1>` both emit dangling `$ref`s to `scheduling.Appointment.v1`/`clinical.Encounter.v1`; `billing.mdl`'s `Invoice.encounterId: ref<clinical.Encounter@1>` emits the same dangling `clinical.Encounter.v1` ref. 11 occurrences total across `InvoiceDb`/`InvoiceReply`/`InvoiceRequest`, `EncounterEvent`/`EncounterReply`/`EncounterRequest`, `ObservationFhirView`, `OutstandingInvoices`, and `AppointmentEvent`/`AppointmentReply`/`AppointmentRequest`. Semantic-identifier references (`practitionerId: PractitionerId`) are unaffected - they correctly `$ref` the semantic type's own component.

**Root cause (read from source, not guessed):** the openapi emitter's field-schema resolver renders a `ref<Domain.Entity@N>` field as a `$ref` to `<Domain>.<Entity>.v<N>` - the component-naming convention used for a *projection* (e.g. `patient.PatientReply.v2`) - but a bare entity/aggregate declaration is never itself emitted as a `components.schemas` entry, only its projections are. The upstream OpenAPI emitter test suite apparently never exercises a `ref<>` field, so the dangling reference is never caught by a real validator.

**Expected:** either emit a component schema for the bare source entity (so the `$ref` resolves), or - more consistent with how other generated targets already treat `ref<>` (e.g. `sql-postgres` emits a `FOREIGN KEY` to the referenced *table*, not the model) - resolve the `$ref` to that entity's `@key` field type (here, the referenced entity's identifier semantic type, e.g. `PatientId`), which is what a `ref<>` field actually carries on the wire.

**Showcase verification:** `tests/integration/test_openapi_contract.py` validates
the complete generated document with `openapi-spec-validator` and checks every
create reply for dangling references.

## 39. `compile --target openapi` emits Modelable-source camelCase property names while `compile --target rust` emits the language-idiomatic snake_case field names as-is on the wire - the two targets disagree about the same model's JSON contract

**Status:** Fixed in v1.9.4. Rust field identifiers
remain snake_case, while serde rename attributes preserve canonical JSON names.

**Discovered:** Task 9.6, writing an HTTP contract test that compares the running Axum API's actual JSON response field names against the generated OpenAPI schema's declared `properties` for the same model.

**Reproduction:**

```bash
modelable compile ./model --target rust --out /tmp/rs
modelable compile ./model --target openapi --out /tmp/oa
grep -n "pub patient_id" /tmp/rs/clinic-core/src/patient/patient_patient_request_v2.rs
python -c "import json; print(list(json.load(open('/tmp/oa/openapi.json'))['components']['schemas']['patient.PatientRequest.v2']['properties']))"
```

**Observed:**

```text
pub patient_id: PatientId,
['patientId', 'legalName', 'preferredName', 'dateOfBirth', 'contact', 'address', 'preferredLanguage', 'alternatePhoneNumbers', 'notes', 'clinicalNotes']
```

`model/patient.mdl` declares fields in Modelable's normal camelCase convention (`patientId`, `legalName`, ...). The `openapi` target's `components.schemas` properties keep that camelCase spelling verbatim. The `rust` target renders the same fields as idiomatic Rust snake_case struct members (`patient_id`, `legal_name`, ...) with no `#[serde(rename = "...")]`/`#[serde(rename_all = "camelCase")]` attribute (confirmed by reading `generated/rust/clinic-core/src/patient/patient_patient_request_v2.rs` - `#[derive(..., serde::Serialize, serde::Deserialize)]` with zero rename attributes), so `serde_json` serializes and deserializes the *wire* JSON in snake_case, not camelCase. A consumer of the generated OpenAPI document (a client generator, a contract-test harness, API documentation) sees `patientId`, but the generated Rust API's actual request/response bodies use `patient_id`. The two targets are both "correct" in isolation and mutually contradictory as a description of one HTTP contract.

**Root cause (read from source, not guessed):** `emitters/openapi.py` copies the Modelable source field spelling directly into the JSON Schema `properties` key. `emitters/rust.py` converts every field name to snake_case for the Rust identifier and, in the same step, uses that same snake_case string as the `serde` wire name (no explicit rename emitted, so serde's default - the Rust identifier itself - becomes the JSON key). Neither emitter is aware of the other's wire-casing choice; there is no cross-target wire-format contract for field-name casing in the normalized graph.

**Expected:** the two targets should agree on the wire representation of the same field. Either (a) `emitters/rust.py` should emit `#[serde(rename = "<camelCase source name>")]` so the Rust wire format matches the OpenAPI (and TypeScript/JSON Schema) convention, or (b) `emitters/openapi.py` should render `properties` keys in the same casing the language target it is meant to document actually puts on the wire (which is target-dependent and therefore not a single answer) - (a) is the only option that keeps one canonical wire contract across every target.

**Showcase verification:** `apps/api/tests/openapi_contract.rs` compares the
running Axum API's response keys directly against the OpenAPI schema; no casing
normalization is needed.

## 40. `compile --target typescript` never marks an optional field `?:` - every field is emitted as required, even `@server` fields and explicit `?` fields

**Status:** Fixed in v1.9.4. TypeScript projection
fields now inherit source optionality and emit `?:` when appropriate.

**Discovered:** Task 10.1, building a patient create form against `generated/typescript/patient.PatientRequest.v2.ts` and finding the TypeScript compiler accepted a call site that omitted `preferredName` (a genuinely optional field) with no error, then separately noticing every field in every generated `.ts` interface lacks `?:` regardless of source optionality.

**Reproduction:**

```bash
sed -n '1,25p' generated/typescript/patient.PatientRequest.v2.ts
```

**Observed:**

```typescript
export interface PatientPatientRequestV2 {
  patientId: string;
  legalName: string;
  preferredName: string;   // model/patient.mdl: preferredName?: string
  dateOfBirth: string;
  contact: ContactDetails;
  address: Address;        // model/patient.mdl: address?: Address
  preferredLanguage: string;
  alternatePhoneNumbers: string[];
  notes: string;           // model/patient.mdl: notes?: string
  clinicalNotes: string;   // model/patient.mdl: clinicalNotes?: string
}
```

Every optional field (`?` in `.mdl`, including every `@server` field like `createdAt`/`updatedAt` which are never client-supplied) is rendered as a required TypeScript property. This is not limited to `patient.PatientRequest.v2` - the same pattern holds across every generated `.ts` file in this showcase (`scheduling.AppointmentReply.v1.bufferDuration`/`reason`/`notes`/`updatedAt`, `clinical.EncounterReply.v1.appointmentId`/`endedAt`/`diagnoses`, `billing.InvoiceReply.v2.encounterId`/`currency`/`dueDate`, ...).

**Root cause (read from source, not guessed):** `emitters/typescript.py`'s field-emission path renders every field's type via `_type_to_ts` but never inspects the field's `optional` flag to decide whether to emit a `?` before the `:`. Every other implemented target that has a language-level optional/nullable concept (`rust`'s `Option<T>`, `python`'s `T | None`, `csharp`'s `T?`, `java`'s boxed/`@Nullable`) does read this flag; only the TypeScript emitter drops it.

**Expected:** emit `fieldName?: T` for any field whose Modelable declaration is optional (including every `@server` field on a `request` projection, which `auto projections ... request exclude [@server]` already excludes entirely - but a hand-written `api {}`/custom projection that keeps an optional `@server` field should still get `?:`), matching the same optionality every other typed target already preserves.

**Showcase verification:** regenerated TypeScript artifacts now mark optional
projection fields with `?:`; the generated types can be used directly by the
web client.

## 41. `compile --target sql-clickhouse` emits a `bloom_filter` secondary index on a composite index that includes a `DateTime64` column - `CREATE TABLE` succeeds but every `INSERT` into the table fails

**Status:** Fix pending upstream review - [ktjn/modelable#417](https://github.com/ktjn/modelable/pull/417) (draft, not yet merged as of this note). Verified by installing that exact PR branch (`git+https://github.com/ktjn/modelable@agent/fix-showcase-gaps#subdirectory=cli`) and re-running this finding's own reproduction: `_clickhouse_secondary_index_type()` now inspects every field's ClickHouse base type and falls back to `minmax` whenever any of them starts with `DateTime`, otherwise keeps `bloom_filter` (`emitters/sql.py`). Re-compiled this showcase's real `model/` with that branch - `billing.InvoiceEvent.v2`'s `idx_by_patient (patient_id, issued_at)` now emits `TYPE minmax`, and a real `INSERT` against that DDL on the pinned ClickHouse 24.8 image succeeds. Not yet re-pinned here since the fix is still a draft PR upstream, not a release.

**Discovered:** Task 13.1 (LSP harness), while re-running the full test suite after re-pinning to v1.9.4. `tests/integration/test_clickhouse_generated_schema.py::test_insert_and_query_back_synthetic_report_rows` started failing with no changes to the showcase's own code - the only change was v1.9.4 newly emitting ClickHouse secondary indexes at all (previously a deferred capability, see `tests/conformance/test_deferred_capabilities.py::test_clickhouse_secondary_indexes_are_now_emitted`).

**Reproduction:**

```bash
docker compose up -d clickhouse
docker compose exec -T clickhouse clickhouse-client --user showcase --password showcase --database showcase --multiquery --query "
DROP TABLE IF EXISTS repro_bloom;
CREATE TABLE repro_bloom (
    patient_id String,
    issued_at Nullable(DateTime64(9)),
    INDEX idx_by_patient (patient_id, issued_at) TYPE bloom_filter GRANULARITY 1
) ENGINE = MergeTree() ORDER BY tuple();
INSERT INTO repro_bloom VALUES ('p1', now64(9));
"
```

**Observed:**

```text
Received exception from server (version 24.8.14):
Code: 36. DB::Exception: Received from localhost:9000. DB::Exception: Unexpected type DateTime64(9) of bloom filter index.. (BAD_ARGUMENTS)
(query: INSERT INTO repro_bloom VALUES ('p1', now64(9));)
```

`CREATE TABLE` (and `SHOW CREATE TABLE`) both succeed - ClickHouse does not validate a `bloom_filter` index's column types at DDL time - so the defect is invisible until the first `INSERT`, which fails hard. The same index type applied to a composite column list containing only `String`/`LowCardinality(String)`/plain `Date` columns (no `DateTime64`) inserts and queries back fine (verified directly: `INDEX idx_by_name (legal_name, date_of_birth) TYPE bloom_filter` where `date_of_birth Date` works; only the `DateTime64`/`Nullable(DateTime64)` case fails). In this showcase's `generated/sql-clickhouse/` output, every table with a `DateTime64` field in a composite secondary index is affected: `billing.InvoiceDb.v2`, `billing.InvoiceEvent.v2`, `billing.InvoiceReply.v2`, `billing.InvoiceRequest.v2` (`idx_by_patient (patient_id, issued_at)`), and `reporting.OutstandingInvoices.v1` (same index, same `issued_at Nullable(DateTime64(9))` column) - five tables. Tables whose composite index columns are all `String`/`Date` (`patient.PatientDb.v2`'s `idx_by_name (legal_name, date_of_birth)`, `scheduling.AppointmentDb.v1`'s `idx_by_patient_day (patient_id, scheduled_date)` where `scheduled_date Date`, etc.) are unaffected.

**Root cause (not yet read from source - Modelable's sql-clickhouse emitter is not vendored into this repo):** the emitter's secondary-index selection appears to pick `bloom_filter` for every multi-column composite index regardless of column type, without special-casing temporal columns. ClickHouse's `bloom_filter` index type does not support `DateTime`/`DateTime64` (only `String`, `FixedString`, numeric, `LowCardinality`, `Array` of those, `Map` keys); `minmax` (or a per-column index split, using `bloom_filter` only for the string columns and `minmax` for the temporal one) is the standard idiomatic choice for a range-queryable date/time column in ClickHouse, verified locally to accept the same insert cleanly.

**Expected:** the sql-clickhouse emitter should either (a) never select `bloom_filter` for an index whose column list includes a `DateTime`/`DateTime64` field - falling back to `minmax` for that index, or (b) split a composite index across column-appropriate index types, so `CREATE TABLE ... INDEX ...` and every subsequent `INSERT` both succeed for the full generated graph.

**Showcase workaround:** `tests/integration/test_clickhouse_generated_schema.py::test_insert_and_query_back_synthetic_report_rows` pins the current reality as an explicit flip test: inserting into `outstanding_invoices` (which carries the affected `idx_by_patient (patient_id, issued_at)` bloom_filter index) is asserted to fail with this exact `DB::Exception: Unexpected type DateTime64(9) of bloom filter index` error, while `daily_schedule` (unaffected - no `DateTime64` column in any of its indexes) still round-trips normally. No permanent DDL-rewriting script was added (`UPSTREAM_POLICY.md` §7); this is Case A per `UPSTREAM_POLICY.md` §6 - fix upstream first.

**Downstream impact (Task 16.1, CI first run):** `billing.InvoiceEvent.v2` (one of the five originally-listed affected tables) is not just a reporting/test fixture - it is the real ClickHouse table `apps/api/src/analytics.rs::record_invoice_event` writes to on every real `POST /api/invoices`, as part of this showcase's actual analytics feature (`GET /api/analytics/clinic`'s `billedTotal`). That write is designed as best-effort (a ClickHouse outage must not fail the already-committed PostgreSQL invoice - see `analytics.rs`'s module doc), so the symptom is silent: the invoice still creates successfully, but `record_invoice_event`'s insert fails server-side with this exact bloom_filter/DateTime64 error and is logged-and-swallowed, so `billedTotal` never reflects that invoice. `apps/api/tests/analytics_api.rs::clinic_analytics_reflects_recorded_events` pins this as a second flip test alongside the ClickHouse-side one above - `billedTotal` is currently asserted to stay `"0.00"` even after a real invoice create, while `paidTotal` (backed by `payment_event`, unaffected - no `DateTime64` column in its indexes) correctly reflects the payment.

## 42. `modelable capabilities --format json` reports `annotation:custom` as `"status": "implemented"`, but the grammar has no production that reaches it - `@custom(...)` is a hard parse error on every attempt

**Status:** Fix pending upstream review - [ktjn/modelable#417](https://github.com/ktjn/modelable/pull/417) (draft, not yet merged as of this note). Verified by installing that exact PR branch and re-running this finding's own reproduction: `modelable.lark`'s `annotation` production gained `"@custom" "(" (IDENT | ESCAPED_STRING) ["," ANNOTATION_EXPR] ")" -> ann_custom`, and the canonical renderer (`compiler/render.py`) now round-trips it back to source text. `modelable validate` on this finding's exact fixture (`@custom("foo", "bar")` on a field) now succeeds where it previously hard-failed with a parse error. Not yet re-pinned here since the fix is still a draft PR upstream, not a release; `tests/conformance/capability-coverage.yaml`'s `annotation:custom` entry stays `excluded` until it is.

**Discovered:** Task 17.1 (finalize command façade), resolving the last `check-capability-coverage.py --strict` gaps before enabling strict mode for good. `annotation:custom` had no manifest entry; while writing a fixture to cover it, every syntax attempt for `@custom(...)` failed to parse.

**Reproduction:**

```bash
cat > /tmp/custom-probe.mdl <<'EOF'
domain thing {
  owner: "t"
  entity Thing @ 1 (additive) {
    @key
    thingId: string
    @custom("foo", "bar")
    name: string
  }
}
EOF
modelable validate /tmp/custom-probe.mdl --strict
```

**Observed:**

```text
Expected one of:
        * __ANON_5
        * RBRACE
        ...
        * IDENT
        * __ANON_3
```

A hard grammar-level parse error - `@custom` is not a recognized annotation token at all. Confirmed by reading the installed 1.9.4 wheel's own grammar directly (`site-packages/modelable/grammar/modelable.lark`, cached locally at the path this showcase's earlier version-pin investigation left under `%TEMP%/ma-diff/m94/modelable-1.9.4/src/modelable/grammar/modelable.lark`): the `annotation` production lists `@key`, `@pii`, `@classification(...)`, `@deprecated(...)`, `@owner(...)`, `@server`, `wire_annotation`, `@pitCutoff(...)`, `@latestBefore(...)`, `@latestOnly` - there is no `@custom` alternative anywhere in the rule. Yet `cli/src/modelable/parser/transformer.py` has a live, fully-implemented `ann_custom` method (`AnnCustom(name=..., expression=...)`) that can never be invoked, because Lark only calls a transformer method when its grammar rule uses `-> ann_custom` as an alias, and no rule does. The same absence holds on a fresh clone of upstream `main` (`github.com/ktjn/modelable`, default branch at time of writing) - this is not a stale-pin artifact.

**Root cause (read from source, not guessed):** `cli/src/modelable/capabilities.py` hardcodes a static capability descriptions table (`"custom": "Attaches an opaque, target-defined annotation"`) that is reported as `"status": "implemented"` for every capability listed there, independent of whether the grammar actually reaches the corresponding transformer method. The `ann_custom` transformer method was written (dead code, unreachable from any grammar rule) but the corresponding `"@custom" "(" ... ")" -> ann_custom` grammar alternative was never added to `annotation:` in `modelable.lark`. `modelable capabilities` never cross-checks its static description table against which transformer methods the grammar can actually produce, so the CLI self-reports a capability that does not exist in the parser at all.

**Expected:** either (a) add the missing `"@custom" "(" IDENT ("," ANNOTATION_EXPR)? ")" -> ann_custom`-shaped grammar alternative so `@custom(...)` actually parses and reaches the existing transformer method, or (b) if `@custom` is intentionally not yet implemented, `modelable capabilities` should report it as `planned`/`deferred`, not `implemented` - the capability-coverage contract this showcase's `check-capability-coverage.py --strict` depends on assumes `implemented` means "a real `.mdl` file can use this today."

**Showcase workaround:** `tests/conformance/capability-coverage.yaml`'s `annotation:custom` entry is `excluded` with a reason pointing at this finding, since no `.mdl` syntax exists to cover it (an `excluded` entry, not a false `product`/`probe` claim). `annotation:latest_only`/`annotation:pit_cutoff`/`annotation:latest_before` are real and do parse/compile (verified: the join-modifier annotations must start on their own physical line after the join's `on` clause, since `EXPRESSION: /[^\n\r{}]+/` greedily consumes the rest of the line the `on` clause sits on) - covered for real by `tests/conformance/valid/join-temporal-modifiers.mdl` and `test_join_temporal_modifiers_compile`.

## 43. `compile --target fhir-profile` emits extension sidecar `StructureDefinition`s that fail the official HL7 FHIR Validator, and references two annotation-marker extension URLs (`.../pii`, `.../classification`) for which no `StructureDefinition` is ever emitted at all

**Status:** Partially fixed by [ktjn/modelable#417](https://github.com/ktjn/modelable/pull/417) (draft, not yet merged as of this note) - both defects originally described here are genuinely resolved, but re-running the real HL7 FHIR Validator against that branch's output surfaces a further, previously-masked defect. See [## 45](#45-compile---target-fhir-profile-emits-extensionurl-elements-with-no-explicit-type-so-snapshot-generation-still-fails-the-official-hl7-fhir-validator-even-after-417) for that residual - this entry's own two defects are confirmed closed by the PR as far as they were originally scoped.

Verified by installing the exact PR branch (`git+https://github.com/ktjn/modelable@agent/fix-showcase-gaps#subdirectory=cli`) and recompiling this showcase's real `model/`: every extension `StructureDefinition` (`_emit_extension_sd` and the two new shared `_emit_annotation_extension_sd` artifacts) now sets `"baseDefinition": "http://hl7.org/fhir/StructureDefinition/Extension"` and `"derivation": "constraint"` (defect 1, fixed), and `pii.fhir.json`/`classification.fhir.json` are now emitted as real top-level artifacts referenced by every `@pii`/`@classification`-annotated field's profile (defect 2, fixed). Running the pinned HL7 FHIR Validator (`6.10.2`) against the PR branch's output for `clinical.PatientFhirView.v1` no longer reports either of this finding's original two error signatures (`sdf-4`/`sdf-8b`/"type Extension can only be used..." and "extension ... could not be found") - but still fails validation overall, for the different reason logged as #45.

**Discovered:** Task 15.4 (HL7 FHIR Validator smoke), running the real official validator (`org.hl7.fhir.core` `validator_cli.jar`, pinned `6.10.2`) against the representative Patient/Observation/Encounter profiles for the first time - no prior task in this showcase had run the actual HL7 validator, only structural JSON checks (`test_fhir_profiles_are_valid_structuredefinition_json`).

**Reproduction:**

```bash
uv run scripts/install-modelable.sh   # or: source scripts/modelable-env.sh
uv run scripts/generate-all.py
./scripts/install-fhir-validator.sh
java -jar tools/validator_cli.jar \
  generated/fhir-profile/clinical.PatientFhirView.v1.fhir.json \
  generated/fhir-profile/clinical.PatientFhirView.v1.ext.patientId.fhir.json \
  generated/fhir-profile/clinical.PatientFhirView.v1.ext.legalName.fhir.json \
  generated/fhir-profile/clinical.PatientFhirView.v1.ext.dateOfBirth.fhir.json \
  -version 4.0.1
```

**Observed:** every one of the three representative `*FhirView` profiles fails, both directly and via their `*.ext.*.fhir.json` sidecars, with two distinct real defects:

```text
-- clinical.PatientFhirView.v1.ext.patientId.fhir.json --
Error @ StructureDefinition.type: The type Extension can only be used as a type when constraining the base definition of the type
Error @ StructureDefinition.snapshot: Constraint failed: sdf-3: 'Each element definition in a snapshot must have a formal definition and cardinalities'
Error @ StructureDefinition.snapshot: Constraint failed: sdf-8b: 'All snapshot elements must have a base definition'
Error @ StructureDefinition: Constraint failed: sdf-4: 'If the structure is not abstract, then there SHALL be a baseDefinition'

-- clinical.PatientFhirView.v1.fhir.json --
Error @ StructureDefinition.snapshot.element[1].extension[0]: The extension http://modelable.io/fhir/StructureDefinition/pii could not be found so is not allowed here
Error @ StructureDefinition.snapshot.element[3].extension[0]: The extension http://modelable.io/fhir/StructureDefinition/classification could not be found so is not allowed here
Error @ StructureDefinition: Error generating Snapshot: Type mismatch processing profile .../clinical.PatientFhirView.v1.ext.patientId at path Patient.extension: The element type is Extension, but the profile ... is for a different type Extension
```

The same two error shapes reproduce identically for `clinical.ObservationFhirView.v1` and `clinical.EncounterFhirView.v1` and every domain's own field-level `*.ext.*.fhir.json` files (`patient.PatientDb.v2.ext.*`, `billing.InvoiceDb.v2.ext.*`, etc.) - this is not specific to one model.

**Root cause (read from source, not guessed):** two independent defects in `emitters/fhir.py` (installed 1.9.4 wheel, `src/modelable/emitters/fhir.py`):

1. `_emit_extension_sd` (the function that emits every per-field `*.ext.<fieldName>.fhir.json` sidecar) builds its `struct_def` dict with `"type": "Extension"` and `"derivation": "specialization"`, but never sets `"baseDefinition"` at all. Per the FHIR spec's own `StructureDefinition` invariants, `type: Extension` is only legal when the structure *constrains* the base `Extension` type (`baseDefinition: http://hl7.org/fhir/StructureDefinition/Extension`, `derivation: constraint`) - a `specialization` with no `baseDefinition` is what `sdf-4`/`sdf-8b` and "can only be used as a type when constraining the base definition" are rejecting. Every extension sidecar this emitter ever produces is invalid FHIR for the same reason.
2. `_extensions()` builds extension-usage entries with `"url": f"{MODELABLE_STRUCTURE_DEFINITION_BASE}/pii"` and `.../classification` for every `@pii`/`@classification(...)`-annotated field, but no function anywhere in `fhir.py` ever emits a `StructureDefinition` artifact *for* those two fixed URLs (`_emit_extension_sd` only emits per-field extensions keyed by field name, never these two shared annotation-marker extensions). Every profile with any `@pii`/`@classification` field - which is most of this showcase's PII-heavy clinical/patient domains - references two permanently unresolvable extension definitions.

**Expected:** (1) `_emit_extension_sd` should set `"baseDefinition": "http://hl7.org/fhir/StructureDefinition/Extension"` and `"derivation": "constraint"` on every emitted extension `StructureDefinition`, matching how every other FHIR profile/extension in the wild is structured; (2) the `fhir-profile` target should also emit `pii.fhir.json`/`classification.fhir.json` (or equivalent) `StructureDefinition` artifacts for the two fixed annotation-marker extension URLs it references, so the full generated `fhir-profile` set - profile plus every extension it points at - validates against the official HL7 FHIR Validator with zero errors.

**Showcase workaround:** `scripts/install-fhir-validator.sh` installs a pinned (`.fhir-validator-version` = `6.10.2`), checksum-verified copy of the real validator; `scripts/validate-fhir-profiles.py` runs it against the three representative Patient/Observation/Encounter profiles (skipping cleanly if Java or the jar isn't available - this is Task 15.4's optional profile, not part of `make acceptance`). `tests/integration/test_generated_artifacts.py::test_fhir_profiles_pass_the_hl7_validator` pins the current reality as an explicit flip test - all three representative profiles are asserted to fail validation with these exact error signatures - rather than a permanent workaround script that rewrites the generated FHIR output (`UPSTREAM_POLICY.md` §7). This is Case A per `UPSTREAM_POLICY.md` §6 - fix upstream first.

## 44. `compile --target avro` crashes on any field with a default value whose Avro type schema is a JSON object rather than a bare type-name string - `TypeError: cannot use 'dict' as a set element`

**Status:** Fix pending upstream review - [ktjn/modelable#417](https://github.com/ktjn/modelable/pull/417) (draft, not yet merged as of this note). Verified by installing that exact PR branch and re-running this finding's own reproduction: `_parse_default` now guards the set-membership check with `isinstance(schema, str) and ...` before testing `schema in {"int", "long", "float", "double"}`, so a `dict`-shaped logical-type schema (e.g. `decimal`) falls through instead of raising. Re-ran the exact fixture from this finding's reproduction below - compiles cleanly, no traceback. Found on upstream `main` in the first place because `avro` did not exist as a capability on the pinned `1.9.4` release at all (`modelable capabilities --format json` reports 20 implemented targets on `1.9.4`, not including `avro`) - this is the canary workflow (Task 16.2) working exactly as designed, discovered on the very first manual canary run, before any re-pin adopts this target.

**Discovered:** Task 16.2 acceptance runs - `.github/workflows/canary.yml` manually triggered against upstream `main` (and, separately, against the exact commit `main` resolved to at trigger time, `0f094cce45285a67380aa23143f8d433d095292c`) both failed identically at the `generate` job, cascading into every other job in the reusable `ci.yml` acceptance suite (all of which run `make generate` before their own work).

**Reproduction:**

```bash
uv tool install --force --python 3.14 "git+https://github.com/ktjn/modelable@main#subdirectory=cli"
mkdir /tmp/avro-repro && cd /tmp/avro-repro
cat > workspace.mdl <<'EOF'
workspace "avro-repro" { description: "probe" }
EOF
cat > thing.mdl <<'EOF'
domain thing {
  owner: "t"
  entity Thing @ 1 (additive) {
    @key
    thingId: string
    tax: decimal(10, 2) = 0
  }
}
EOF
modelable compile . --target avro --out ./out --registry ./registry.db --registry-ids ./registry-ids.lock
```

**Observed:**

```text
Traceback (most recent call last):
  ...
  File ".../modelable/emitters/avro.py", line 66, in _emit_record
    schema = _record_schema(name, version.fields, version.version, "model", ref, context)
  File ".../modelable/emitters/avro.py", line 104, in _record_schema
    entry["default"] = _parse_default(model_field.default, field_schema)
  File ".../modelable/emitters/avro.py", line 226, in _parse_default
    if schema in {"int", "long", "float", "double"}:
TypeError: cannot use 'dict' as a set element (unhashable type: 'dict')
```

Confirmed by reading the actually-emitted Avro schema for the same field with no default (`tax: decimal(10, 2)`, no `= 0`) - the field's `type` renders as a JSON *object*, not a bare string:

```json
{
  "name": "tax",
  "type": { "type": "bytes", "logicalType": "decimal", "precision": 10, "scale": 2 }
}
```

`string`/`int`/`bool`/etc. fields with a default (verified: `label: string = "..."`, `label?: string = "..."`, `quantity: int = 1`) all compile fine - the crash is specific to any field whose Avro type is a logical-type object (at minimum `decimal`; likely also `date`/`timestamp`/`uuid` and any other logicalType-based mapping, not independently verified here) combined with a `.mdl`-declared default value. This showcase's own `model/billing.mdl` (`tax: decimal(10, 2) = 0`, twice) and `model/clinical.mdl`/`model/scheduling.mdl`'s enum-with-default fields would hit the same code path if `avro` is ever adopted as an implemented target here.

**Root cause (read from source, not guessed - `emitters/avro.py`, installed from `git+https://github.com/ktjn/modelable@main`):** `_parse_default` (line ~226) branches on the field's already-rendered Avro `type` value (`schema`, a `str` for primitive types but a `dict` for any logical/complex type) with `if schema in {"int", "long", "float", "double"}:` - a Python `in` check against a `set` literal, which requires `schema` to be hashable. A `dict` is never hashable, so this raises `TypeError` instead of either matching or falling through to the (presumably intended) "else" branch for non-numeric-primitive types. The function was clearly never exercised with a defaulted decimal/logical-type field before this crash - `_record_schema` calls it unconditionally for every field with a `default` set, regardless of the field's underlying type shape.

**Expected:** `_parse_default` should check `isinstance(schema, str)` (or equivalent) before the set-membership test, so a logical-type/complex `dict` schema falls through to whatever this function's non-primitive-type branch is meant to do (which may itself need a real implementation for decimal/date/timestamp/uuid defaults, not just a crash-free no-op) rather than raising an unhandled `TypeError`.

**Showcase workaround:** None needed - `avro` is not (yet) an implemented target on the pinned `1.9.4` release this showcase depends on, so no `.mdl` file, generation step, or test in this repository is affected today. Logged here purely as a canary finding (`UPSTREAM_POLICY.md` §6 Case A) so it is not rediscovered from scratch when a future re-pin adopts a release that includes the `avro` target.

## 45. `compile --target fhir-profile` emits `Extension.url` elements with no explicit type, so snapshot generation still fails the official HL7 FHIR Validator even after #417

**Status:** Still open after two revisions of [ktjn/modelable#418](https://github.com/ktjn/modelable/pull/418) (draft). Verified by installing each exact commit and re-running this finding's own reproduction against the real HL7 FHIR Validator (`6.10.2`):

- **First revision (`cb707c7b`):** added `"type": [{"code": "uri"}]` to `Extension.url` in both `_emit_extension_sd` and `_emit_annotation_extension_sd`. `pii.fhir.json`/`classification.fhir.json` (shared annotation-marker extensions with a simple primitive value) validated clean (0 errors). But the per-field extensions for value-typed/named-type fields (`.ext.patientId`, `.ext.legalName`, `.ext.dateOfBirth`) still failed with `sdf-3` and `Extension.value[x]: invalid constrained type BackboneElement` - the diff never touched `_fhir_type()`, the actual source. `clinical.PatientFhirView.v1.fhir.json` was byte-for-byte unchanged (5 errors, 1 warning, 1 note).
- **Second revision (`89b41303`, current head):** PR description now explicitly claims to also resolve `value[x]` to "underlying valid FHIR datatypes instead of invalid BackboneElement constraints," and admits the validator wasn't run locally ("the real HL7 validator is not configured locally; the validator findings supplied for this PR are covered by the generated type/cardinality fixes and regression tests" - exactly the gap this showcase's review process exists to catch). Re-running the real validator against this commit: the individual extension files did improve - `.ext.patientId`/`.ext.legalName`/`.ext.dateOfBirth` dropped from a `BackboneElement` type error to just the cascading `sdf-3` (1 error each), and `pii`/`classification` remain clean. But `clinical.PatientFhirView.v1.fhir.json` **got worse, not better**: 5 errors → 7 errors, with two *new* errors not present before either revision: `Error @ StructureDefinition.differential.element[1].type[0]: The type 1 is not in the list of allowed type string in the profile [BackboneElement]` and the identical error on `snapshot.element[1].type[0]`. The fix that resolved `value[x]` for the extension files appears to have shifted a `BackboneElement`-typed reference into the top-level Patient profile's own `Patient.contact` element instead of eliminating it. Full reproduction and observed output below reflect the **first-revision** run (kept as the citable baseline); the second-revision delta is summarized here since it is a moving target on a draft PR.

**Discovered:** Reviewing PR #417 for this showcase's own logged findings. Installing that exact branch (`git+https://github.com/ktjn/modelable@agent/fix-showcase-gaps#subdirectory=cli`), recompiling this showcase's real `model/` to `fhir-profile`, and running the pinned HL7 FHIR Validator (`6.10.2`) against the output no longer reproduces #43's two original error signatures, but still fails validation for a different reason that #43's validator run never reached (short-circuited earlier by the more fundamental `baseDefinition` errors #417 fixes).

**Reproduction:**

```bash
uv tool install --force --python 3.14 "git+https://github.com/ktjn/modelable@agent/fix-showcase-gaps#subdirectory=cli"
modelable compile ./model --target fhir-profile --out /tmp/fhir-out --registry /tmp/reg.db --registry-ids /tmp/ids.lock
java -jar tools/validator_cli.jar \
  /tmp/fhir-out/clinical.PatientFhirView.v1.fhir.json \
  /tmp/fhir-out/clinical.PatientFhirView.v1.ext.patientId.fhir.json \
  /tmp/fhir-out/clinical.PatientFhirView.v1.ext.legalName.fhir.json \
  /tmp/fhir-out/clinical.PatientFhirView.v1.ext.dateOfBirth.fhir.json \
  /tmp/fhir-out/pii.fhir.json \
  /tmp/fhir-out/classification.fhir.json \
  -version 4.0.1
```

**Observed:**

```text
-- clinical.PatientFhirView.v1.ext.patientId.fhir.json --
*FAILURE*: 3 errors, 2 warnings
Error @ StructureDefinition.snapshot: Constraint failed: sdf-3: 'Each element definition in a snapshot must have a formal definition and cardinalities'
Error @ StructureDefinition: Error generating Snapshot: StructureDefinition .../clinical.PatientFhirView.v1.ext.patientId at Extension.value[x]: invalid constrained type BackboneElement from base64Binary, boolean, canonical, ... in http://hl7.org/fhir/StructureDefinition/Extension
Error @ StructureDefinition.snapshot.element[1]: The element Extension.url has no assigned types, and no content reference

-- pii.fhir.json / classification.fhir.json --
*FAILURE*: 1 errors, 2 warnings
Error @ StructureDefinition.snapshot.element[1]: The element Extension.url has no assigned types, and no content reference

-- clinical.PatientFhirView.v1.fhir.json --
*FAILURE*: 5 errors, 1 warnings, 1 notes
Error @ StructureDefinition.differential.element[1]: No match found for Patient.contact in the generated snapshot: check that the path and definitions are legal in the differential (including order)
Error @ StructureDefinition: The profile ...clinical.PatientFhirView.v1 has 1 element in the differential (id: Patient.contact) that don't have a matching element in the snapshot
Error @ StructureDefinition.snapshot.element[2]: The element Patient.extension has no assigned types, and no content reference
```

Every extension `StructureDefinition` this emitter produces (both `_emit_extension_sd`'s per-field extensions and #417's new `_emit_annotation_extension_sd` shared `pii`/`classification` extensions) declares an `Extension.url` element (with `fixedUri` set) but never gives it an explicit `"type"` array. FHIR's own base `Extension.url` element is typed `uri`; a constraining profile that overrides `fixedUri` still needs to either inherit or restate that type for the validator's snapshot generator to resolve `Extension.value[x]`'s base correctly - without it, snapshot generation aborts with "has no assigned types, and no content reference," which cascades into every dependent validation (including the top-level profile's own `Patient.contact`/`Patient.extension` differential-vs-snapshot match, since the extension's snapshot never successfully generates for the profile to constrain against).

**Root cause, url-type half (fixed by #418's first revision):** `emitters/fhir.py` on PR #417's branch had `_emit_extension_sd`'s `elements` list set `"id": "Extension.url"`, `"path": "Extension.url"`, `"min": 1`, `"max": "1"`, `"fixedUri": ext_url` - no `"type"` key, and `_emit_annotation_extension_sd` had the identical gap. #418's first revision's diff was exactly two one-line additions of `"type": [{"code": "uri"}]` to those two `Extension.url` elements - confirmed by reading the PR's diff directly, not just its description.

**Root cause, `value[x]` half (fixed for the extension files by #418's second revision, but appears to have moved the problem into the top-level profile - read from `emitters/fhir.py` on PR #418's branch at `cb707c7b`):** `_fhir_type(field_type, source_field=...)` (module-level helper, ~line 434) unconditionally mapped `isinstance(field_type, (NamedType, ObjectType))` to `[{"code": "BackboneElement"}]`. `clinical.PatientFhirView.v1`'s `patientId`/`legalName`/`dateOfBirth` fields resolve to a `NamedType`/value-type, so `_extension_sd_value_element()` called `_fhir_type()` and got back `BackboneElement` for `Extension.value[x]` - which FHIR's own base `Extension.value[x]` element does not permit as a constrained type (its allowed type list is primitives/complex-datatypes only, never `BackboneElement`). The second revision (`89b41303`) changed this - the individual extension files no longer show the `BackboneElement` `value[x]` error - but `clinical.PatientFhirView.v1.fhir.json` itself now shows two *new* `BackboneElement`-type errors on `Patient.contact` (`differential.element[1].type[0]` and `snapshot.element[1].type[0]`) that did not exist in either the pre-#417, first-#418-revision, or #417-only states. The showcase has not yet inspected the second revision's diff line-by-line to pin the exact new root cause (the PR is a moving target); this is recorded as an observation pending that follow-up.

**Expected:** the full generated `fhir-profile` set - extensions and the top-level profile together - validates with zero errors against the real HL7 FHIR Validator, not just the individual extension files in isolation.

**Showcase workaround:** None yet - `tests/integration/test_generated_artifacts.py::test_fhir_profiles_pass_the_hl7_validator` still pins the pinned-`1.9.4` failure signatures from #43 (unaffected by this finding, since the showcase has not re-pinned to #417's or #418's unreleased branches). Will need updating once a release including a full fix is adopted.
