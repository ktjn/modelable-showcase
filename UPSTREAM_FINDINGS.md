# Modelable Upstream Findings Log

**Status:** living document — append an entry every time this showcase discovers real Modelable behavior that diverges from its own documentation, crashes instead of producing a diagnostic, or fails to implement something its own source code visibly intends to (reserved-but-unused diagnostic codes, dead IR variants, etc.).

**Purpose:** `UPSTREAM_POLICY.md` §1 requires that a gap discovered here get "exposed rather than hidden." A finding scattered across a commit message or a PR description satisfies the letter of that a single time, but is invisible to the next person unless they read the entire git history. This file is the one place all of them are supposed to be visible at once.

**Not this file's job:** process (`UPSTREAM_POLICY.md` owns *how* to handle a gap), requirements (`SPEC.md` owns *what* the showcase must do), or task sequencing (`IMPLEMENTATION_PLAN.md` owns *when*). This file only records *what was actually observed*, against *which exact version*, with a *minimal reproduction*. When SPEC.md needs to state a consequence of a finding here (e.g. "this negative fixture doesn't exist because the behavior it would test doesn't exist"), it should say so briefly and point back here for the detail, not restate the detail.

**Every entry needs:** a reproduction a stranger can run against the pinned release without any of this repo's other context, the exact observed output, what was expected instead, which `UPSTREAM_POLICY.md` §6 case it falls under, and the workaround (if any) this showcase used, with a pointer to where.

**Verified against:** `modelable==1.7.0` (the pinned release, see `.modelable-version`) unless noted otherwise. Several entries were re-checked against upstream `main` at commit `e2fe6ac54e6cba42982c5bbeeacad95524393762` specifically because the finding looked like it might already be fixed there — the log says explicitly whenever that check happened, and doesn't claim it otherwise.

## Status summary

| # | Finding | Category | Case |
|---|---|---|---|
| 1 | [`@wire(json: {...})` crashes instead of diagnosing an unsupported key](#1-wirejson--crashes-instead-of-diagnosing-an-unsupported-key) | Crash | A |
| 2 | [`ref<Model@N#hash>` cannot pin most real SHA-256 signatures](#2-refmodelnhash-cannot-pin-most-real-sha-256-signatures) | Grammar gap | A |
| 3 | [`group by` cannot take a function-call expression](#3-group-by-cannot-take-a-function-call-expression) | Grammar gap | A |
| 4 | [`where` followed by `pick`/`omit` on the next line fails to parse](#4-where-followed-by-pickomit-on-the-next-line-fails-to-parse) | Grammar gap | A |
| 5 | [Unresolvable/ambiguous bare semantic-type field references silently degrade instead of erroring](#5-unresolvableambiguous-bare-semantic-type-field-references-silently-degrade-instead-of-erroring) | Missing diagnostic | A |
| 6 | [`compile --target protobuf` crashes on reservation reuse instead of diagnosing it](#6-compile---target-protobuf-crashes-on-reservation-reuse-instead-of-diagnosing-it) | Crash | A |
| 7 | [CEL type-mismatch checking is not implemented](#7-cel-type-mismatch-checking-is-not-implemented) | Missing feature | A |
| 8 | [`ref<Model @ >=N <M>>` version-range notation is easy to double-bracket](#8-refmodel--n-m-version-range-notation-is-easy-to-double-bracket) | Docs clarity | C |

"Case" refers to `UPSTREAM_POLICY.md` §6's decision tree. All findings below are Case A ("Modelable is wrong or incomplete") except #8, which is Case C (an intentional-looking design whose documentation example is easy to misread) — kept here anyway because misreading it produces a real parse error, which is exactly the kind of thing this log exists to save the next person from re-discovering.

None of these have been taken upstream yet (no upstream issue filed, no upstream PR opened). Per `UPSTREAM_POLICY.md` §1 that is the required next step for each Case A entry; this log is the "reproduce the gap" step, not a substitute for the rest of the sequence.

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
