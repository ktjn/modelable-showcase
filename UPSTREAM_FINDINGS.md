# Modelable Upstream Findings Log

**Status:** living document — append an entry every time this showcase discovers real Modelable behavior that diverges from its own documentation, crashes instead of producing a diagnostic, or fails to implement something its own source code visibly intends to (reserved-but-unused diagnostic codes, dead IR variants, etc.).

**Purpose:** `UPSTREAM_POLICY.md` §1 requires that a gap discovered here get "exposed rather than hidden." A finding scattered across a commit message or a PR description satisfies the letter of that a single time, but is invisible to the next person unless they read the entire git history. This file is the one place all of them are supposed to be visible at once.

**Not this file's job:** process (`UPSTREAM_POLICY.md` owns *how* to handle a gap), requirements (`SPEC.md` owns *what* the showcase must do), or task sequencing (`IMPLEMENTATION_PLAN.md` owns *when*). This file only records *what was actually observed*, against *which exact version*, with a *minimal reproduction*. When SPEC.md needs to state a consequence of a finding here (e.g. "this negative fixture doesn't exist because the behavior it would test doesn't exist"), it should say so briefly and point back here for the detail, not restate the detail.

**Every entry needs:** a reproduction a stranger can run against the pinned release without any of this repo's other context, the exact observed output, what was expected instead, which `UPSTREAM_POLICY.md` §6 case it falls under, and the workaround (if any) this showcase used, with a pointer to where.

**Verified against:** `modelable==1.7.0` (the pinned release, see `.modelable-version`) unless noted otherwise. Several entries were re-checked against upstream `main` at commit `e2fe6ac54e6cba42982c5bbeeacad95524393762` specifically because the finding looked like it might already be fixed there — the log says explicitly whenever that check happened, and doesn't claim it otherwise.

## Status summary

| # | Finding | Category | Case | Status |
|---|---|---|---|---|
| 1 | [`@wire(json: {...})` crashes instead of diagnosing an unsupported key](#1-wirejson--crashes-instead-of-diagnosing-an-unsupported-key) | Crash | A | Fixed in [ktjn/modelable#354](https://github.com/ktjn/modelable/pull/354) (open, not yet merged/released) |
| 2 | [`ref<Model@N#hash>` cannot pin most real SHA-256 signatures](#2-refmodelnhash-cannot-pin-most-real-sha-256-signatures) | Grammar gap | A | Fixed in #354 |
| 3 | [`group by` cannot take a function-call expression](#3-group-by-cannot-take-a-function-call-expression) | Grammar gap | A | Fixed in #354 |
| 4 | [`where` followed by `pick`/`omit` on the next line fails to parse](#4-where-followed-by-pickomit-on-the-next-line-fails-to-parse) | Grammar gap | A | Fixed in #354 |
| 5 | [Unresolvable/ambiguous bare semantic-type field references silently degrade instead of erroring](#5-unresolvableambiguous-bare-semantic-type-field-references-silently-degrade-instead-of-erroring) | Missing diagnostic | A | Fixed in #354 |
| 6 | [`compile --target protobuf` crashes on reservation reuse instead of diagnosing it](#6-compile---target-protobuf-crashes-on-reservation-reuse-instead-of-diagnosing-it) | Crash | A | Fixed in #354 |
| 7 | [CEL type-mismatch checking is not implemented](#7-cel-type-mismatch-checking-is-not-implemented) | Missing feature | A | Fixed in #354 |
| 8 | [`ref<Model @ >=N <M>>` version-range notation is easy to double-bracket](#8-refmodel--n-m-version-range-notation-is-easy-to-double-bracket) | Docs clarity | C | N/A — no code fix needed |
| 9 | [A second `auto projections` declaration for another version of the same model is silently dropped](#9-a-second-auto-projections-declaration-for-another-version-of-the-same-model-is-silently-dropped) | Silent data loss | A | Fixed in #354 |
| 10 | [`modelable diff` never reports governance (access/classification/@pii) changes for entities and aggregates, only for projections](#10-modelable-diff-never-reports-governance-accessclassificationpii-changes-for-entities-and-aggregates-only-for-projections) | Missing diagnostic | A | Fixed in #354 |
| 11 | [`reserved protobuf { names: [...] }` must use the generated snake_case Protobuf name, not the Modelable source field name, for cross-version reuse checks](#11-reserved-protobuf-names--must-use-the-generated-snake_case-protobuf-name-not-the-modelable-source-field-name-for-cross-version-reuse-checks) | Inconsistent behavior | A | Fixed in #354 |
| 12 | [`compile --target typescript` never imports a field's semantic type - every semantic-typed field is a compile error](#12-compile---target-typescript-never-imports-a-fields-semantic-type---every-semantic-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Fixed in #354 |
| 13 | [`compile --target typescript` never emits any imports at all for auto-generated projections (Db/Request/Reply/Event)](#13-compile---target-typescript-never-emits-any-imports-at-all-for-auto-generated-projections-dbrequestreplyevent) | Crash (broken generated code) | A | Fixed in #354 |
| 14 | [`compile --target rust` loses named-type resolution for optional array fields specifically](#14-compile---target-rust-loses-named-type-resolution-for-optional-array-fields-specifically) | Crash (broken generated code) | A | Fixed in [ktjn/modelable#355](https://github.com/ktjn/modelable/pull/355) (open, not yet merged/released) |
| 15 | [`compile --target csharp` never resolves named-type references to the emitted stable type name - every value-type-typed field is a compile error](#15-compile---target-csharp-never-resolves-named-type-references-to-the-emitted-stable-type-name---every-value-type-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Open |
| 16 | [`compile --target csharp` never emits semantic types at all - every semantic-typed field is a compile error](#16-compile---target-csharp-never-emits-semantic-types-at-all---every-semantic-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Open |
| 17 | [`compile --target java` never resolves named-type references to the emitted stable type name - every value-type-typed field is a compile error](#17-compile---target-java-never-resolves-named-type-references-to-the-emitted-stable-type-name---every-value-type-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Open |
| 18 | [`compile --target java` never emits semantic types at all - every semantic-typed field is a compile error](#18-compile---target-java-never-emits-semantic-types-at-all---every-semantic-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Open |
| 19 | [`compile --target python` never resolves named-type references to the emitted stable type name - every value-type-typed annotation is a NameError](#19-compile---target-python-never-resolves-named-type-references-to-the-emitted-stable-type-name---every-value-type-typed-annotation-is-a-nameerror) | Crash (broken generated code) | A | Open |
| 20 | [`compile --target python` never emits semantic types at all - every semantic-typed annotation is a NameError](#20-compile---target-python-never-emits-semantic-types-at-all---every-semantic-typed-annotation-is-a-nameerror) | Crash (broken generated code) | A | Open |
| 21 | [`compile --target go` never resolves named-type references to the emitted stable type name - every value-type-typed field is a compile error](#21-compile---target-go-never-resolves-named-type-references-to-the-emitted-stable-type-name---every-value-type-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Open |
| 22 | [`compile --target go` never emits semantic types at all - every semantic-typed field is a compile error](#22-compile---target-go-never-emits-semantic-types-at-all---every-semantic-typed-field-is-a-compile-error) | Crash (broken generated code) | A | Open |
| 23 | [`compile --target grpc` emits one standalone service file per model into the same `modelable.<domain>.<version>.scalable` package - the full emitted graph cannot be compiled together](#23-compile---target-grpc-emits-one-standalone-service-file-per-model-into-the-same-modelabledomainversionscalable-package---the-full-emitted-graph-cannot-be-compiled-together) | Crash (broken generated code) | A | Open |

"Case" refers to `UPSTREAM_POLICY.md` §6's decision tree. All findings below are Case A ("Modelable is wrong or incomplete") except #8, which is Case C (an intentional-looking design whose documentation example is easy to misread) — kept here anyway because misreading it produces a real parse error, which is exactly the kind of thing this log exists to save the next person from re-discovering.

**#1–#7, #9–#13** were all independently reproduced and confirmed fixed by re-running each finding's exact reproduction against a local build of [ktjn/modelable#354](https://github.com/ktjn/modelable/pull/354) at commit `81f2288ac08d7ba006a78aee4a9e07b51cdd57c7` (`agent/fix-upstream-findings`, merged with upstream `main` at the time of verification). That PR's own gates were verified too: `ruff check`/`ruff format --check` clean, the mypy baseline ratchet reports 0 new errors, and the upstream `pytest tests/` suite passes (2095 passed, 49 skipped). This showcase's own full suite passes 125/125 against that build once `generated/` is refreshed. Per `UPSTREAM_POLICY.md` §1 step 6 ("run this showcase against the upstream branch/commit... while the full suite is still being built") this counts as that verification step — but steps 7–9 (merge/release Modelable, update `.modelable-version`, complete the dependent showcase slice) are still outstanding: **PR #354 is not yet merged, and `.modelable-version` still pins `1.7.0`, the pre-fix release.** Do not treat any of #1–#13 as resolved in this showcase's own behavior until the pin actually moves - `apps/web/src/generated-types.ts`'s workaround for #12/#13, for example, is still active and necessary against the currently pinned release.

**#14** was discovered after #354 already existed, is not yet addressed by it, and has not been taken upstream (no issue filed, no PR). Per `UPSTREAM_POLICY.md` §1 that is the required next step. **#14 was confirmed fixed in [ktjn/modelable#355](https://github.com/ktjn/modelable/pull/355)** (verified by re-running its exact reproduction against that PR's commit `b474232`), which is open but not yet merged — so `.modelable-version` still pins `1.7.0` and this showcase's Rust probe still asserts the pre-fix failure, exactly like the #1–#13 note above.

**#15 and #16** (the C# emitter, discovered together during Task 7.2) were verified against upstream `main` at commit `22eaf4c` (`fix: tolerate rewritten main history in validation (#356)`): `emitters/csharp.py` is byte-identical to the pinned `1.7.0` release on that branch (its last real change is the naming-helper consolidation in #313, long before #354/#355/#356), so neither is fixed or even touched there yet. They share a root-cause neighborhood but are distinct bugs with distinct fixes, so they are logged as two entries below rather than one. Neither has been taken upstream yet — per `UPSTREAM_POLICY.md` §1 that is the required next step.

**#17 and #18** (the Java emitter, discovered together during Task 7.3) are the C# pair's exact analogues for the `java` target. They were verified against upstream `main` at the same commit `22eaf4c`: `emitters/java.py` is byte-identical to the pinned `1.7.0` release there (same #313 last-change history as `csharp.py`), so neither is fixed or touched upstream either. They are logged as two separate entries below (distinct bugs, distinct fixes), and neither has been taken upstream yet.

**#19–#22** (the Python and Go emitters, discovered together during Task 7.4) complete the same named-type/semantic-type picture for the last two first-class target languages. Both were verified against upstream `main` at the same commit `22eaf4c`: `emitters/python.py` and `emitters/go.py` are both byte-identical to the pinned `1.7.0` release there (both share the same #313 last-change history), so neither pair is fixed or touched upstream either. The Go pair (#21/#22) is a hard compile failure exactly like the C#/Java ones; the Python pair (#19/#20) is *latent* — because every generated module starts with `from __future__ import annotations`, the broken references are lazy string annotations, so modules import and dataclasses instantiate fine, and the breakage only surfaces when the annotations are actually resolved (`typing.get_type_hints` raises `NameError`) or consumed by any typed tooling. All four are logged as separate entries below (distinct bugs per emitter, distinct fixes), and none has been taken upstream yet.

**#23** (the gRPC emitter, discovered during Task 7.5 while running the first real `protoc` over the whole `generated/grpc/` output) is a different bug class from #15–#22: no named-type or semantic-type reference is involved. It was verified against upstream `main` at the same commit `22eaf4c`: `emitters/grpc.py` is byte-identical to the pinned `1.7.0` release there (its last real change is #172/#170), so it is not fixed or touched upstream either. It has not been taken upstream yet. The protobuf target is *not* affected — the full `generated/protobuf/` graph (44 files) compiles cleanly with `protoc`, and `modelable compile --descriptor-set` succeeds for both targets (it compiles each artifact individually, which is exactly the per-file mode #23 leaves working).

---

## 1. `@wire(json: {...})` crashes instead of diagnosing an unsupported key

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
