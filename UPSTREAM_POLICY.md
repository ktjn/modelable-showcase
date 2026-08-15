# Modelable Showcase Upstream Policy

**Status:** mandatory implementation policy  
**Applies to:** all tasks in `SPEC.md` and `IMPLEMENTATION_PLAN.md`  
**Upstream:** `ktjn/modelable`

This document overrides any conflicting implementation shortcut in `SPEC.md` or `IMPLEMENTATION_PLAN.md`.

## 1. Core rule

`modelable-showcase` is a downstream acceptance product for Modelable. It MUST expose gaps in Modelable rather than hide them.

When the showcase needs a contract, emitter, language feature, validation rule, compatibility behavior, or generated artifact that Modelable cannot provide correctly, the default action is:

1. reproduce the gap against the current intended Modelable baseline;
2. verify the gap against upstream `ktjn/modelable@main`;
3. add or update upstream Modelable tests that demonstrate the missing/broken behavior;
4. implement the fix or feature in `ktjn/modelable`;
5. run Modelable's own required gates;
6. run this showcase against the upstream branch/commit using `MODELABLE_REF=<ref> make acceptance` or the narrowest available showcase gate while the full suite is still being built;
7. merge/release Modelable according to its normal process;
8. update the showcase pin when appropriate;
9. only then complete the showcase slice that depends on the capability.

Do not solve an upstream Modelable gap by permanently adding a second schema system, handwritten equivalent contract, post-processing generated output, or target-specific fork inside this repository.

## 2. OpenAPI is Modelable-owned

OpenAPI is a required product contract for this showcase.

The OpenAPI document MUST be generated directly by Modelable from `.mdl` sources.

Forbidden alternatives:

- handwritten `openapi.yaml` / `openapi.json`;
- Axum annotations or route macros as the canonical OpenAPI source;
- generating OpenAPI from Rust types after Modelable generation;
- generating OpenAPI from TypeScript types;
- maintaining a parallel API schema in JSON Schema, TypeSpec, protobuf, or another IDL and treating that as canonical;
- post-processing another Modelable target into an independently maintained OpenAPI contract;
- accepting a placeholder OpenAPI document that is not derived from the same normalized Modelable graph as the other generated artifacts.

The `.mdl` workspace remains the source of truth.

## 3. Known first upstream gap: OpenAPI emitter

At the time this policy was written, the current Modelable target manifest does not advertise `openapi` as an implemented code-generation target. The language documentation has historically accepted OpenAPI in target vocabulary while describing the actual emitter as deferred.

Therefore OpenAPI is the first known upstream gap discovered by this showcase.

Before the showcase implements its stable HTTP API contract, an implementation agent MUST add a real OpenAPI target to `ktjn/modelable` unless upstream has already gained one by the time the task starts.

First check:

```bash
modelable capabilities --format json
modelable compile --help
```

If an implemented `openapi` target exists, use it and verify it satisfies this policy. Do not reimplement it.

If it does not exist, work upstream first.

## 4. Required upstream OpenAPI behavior

The exact upstream design belongs in Modelable, but the showcase requires at least the following observable contract before OpenAPI can be considered covered.

### 4.1 Generation

A supported command MUST generate OpenAPI deterministically, using the normal compiler target mechanism, for example:

```bash
modelable compile ./model --target openapi --out ./generated/openapi
```

Use the actual final target name exposed by Modelable. The showcase MUST discover it through `modelable capabilities --format json` rather than special-case a hidden command.

### 4.2 Source semantics

The generated OpenAPI schema MUST originate from the normalized Modelable graph and preserve the Modelable contract semantics that matter to an HTTP API, including where representable:

- model/projection identity and version;
- required versus optional fields;
- enums;
- arrays/maps/objects;
- semantic types;
- references;
- request/reply projection shape;
- field descriptions/metadata where available;
- Modelable extensions for metadata that OpenAPI cannot express natively without loss.

OpenAPI MUST NOT silently become a second semantic authority.

### 4.3 API surface

The showcase should model HTTP-facing contracts through explicit request/reply projections. The OpenAPI emitter MUST consume those contracts rather than exposing every canonical persistence entity indiscriminately.

If route/operation declaration syntax is missing from Modelable, that is another upstream gap. Add the smallest general Modelable feature required to describe operations cleanly. Do not encode route metadata in showcase-only side files merely to unblock generation.

If Modelable intentionally chooses a convention-based operation mapping instead of new syntax, that convention MUST be documented and tested upstream before the showcase relies on it.

### 4.4 Validation

Upstream Modelable MUST have tests that prove generated OpenAPI is structurally valid and deterministic.

The showcase MUST additionally validate the generated document with an independent OpenAPI parser/validator and use it in downstream API contract tests.

### 4.5 Capability manifest

Once implemented upstream, `modelable capabilities --format json` MUST report OpenAPI as implemented. The showcase capability coverage manifest MUST then classify it as `product`.

## 5. Showcase OpenAPI consumption

After upstream OpenAPI exists, the showcase MUST:

1. generate OpenAPI during `make generate`;
2. place it under disposable `generated/openapi/` output;
3. validate it independently;
4. expose the generated contract to developers, e.g. through a static API-docs route or local Swagger UI/Scalar viewer;
5. run HTTP contract tests against the running Axum API;
6. fail CI when routes/request/reply behavior drifts from the generated Modelable OpenAPI contract;
7. include OpenAPI in determinism tests;
8. include OpenAPI in `tests/conformance/capability-coverage.yaml` as product-consumed.

A documentation viewer MAY be handwritten configuration. The OpenAPI document itself MUST NOT be handwritten.

## 6. Gap handling decision tree

For every mismatch found while implementing the showcase:

### Case A — Modelable is wrong or incomplete

Examples:

- emitter output does not compile;
- generated OpenAPI is invalid;
- a legal `.mdl` construct cannot be represented by an implemented target without an explicit diagnostic;
- metadata/lineage/classification disappears unexpectedly;
- compatibility classification is incorrect;
- generated language code cannot be consumed normally;
- required product behavior exposes a generally useful missing language/compiler capability.

Action: fix Modelable upstream first.

### Case B — Showcase is using Modelable incorrectly

Examples:

- wrong `.mdl` syntax;
- relying on a deferred capability;
- assuming an emitter guarantee not documented by upstream;
- incorrect mapping between generated types and runtime infrastructure.

Action: fix the showcase. Do not change Modelable merely to preserve a bad downstream assumption.

### Case C — Modelable has an intentional documented limitation

Action:

1. verify the limitation is still intentional on upstream `main`;
2. decide whether the limitation prevents a meaningful real product;
3. if yes, treat it as an upstream product gap and improve Modelable;
4. if no, keep a narrow explicit showcase boundary/test for the limitation.

Never silently work around it.

## 7. No local patch layer

The following anti-patterns are prohibited unless used temporarily only to produce a failing reproduction for an upstream fix:

```text
scripts/fix-generated-openapi.py
scripts/patch-rust-output.py
scripts/rewrite-sql.py
generated-overrides/
handwritten mirror DTOs
handwritten mirror schemas
```

If generated output needs systematic rewriting to become usable, the emitter is incomplete. Fix the emitter.

Normal build glue is allowed when it does not change contract semantics, e.g. copying generated files, invoking formatters required by a target ecosystem, ordering DDL files, or packaging generated artifacts.

## 8. Upstream change requirements

Every upstream change discovered through the showcase MUST include, where applicable:

- a minimal upstream regression test reproducing the gap;
- implementation in the correct compiler/parser/emitter layer;
- capability status update when a capability moves from deferred to implemented;
- documentation updates;
- changelog entry for user-visible behavior;
- compatibility tests when wire/schema compatibility is affected;
- downstream verification against this showcase using the exact upstream branch/commit.

The upstream PR description SHOULD state that the gap was found by `modelable-showcase` and include the showcase verification command/result.

## 9. Branch and dependency workflow

A showcase branch may depend temporarily on an unmerged Modelable branch.

Use:

```bash
MODELABLE_REF=<upstream-branch-or-sha> make acceptance
```

Do not vendor upstream source into this repository.

Do not merge a showcase change that relies on unpublished/unmerged Modelable behavior unless the repository intentionally supports that dependency state. Normal sequence is upstream Modelable first, showcase second.

## 10. Required changes to the implementation plan

Implementation agents MUST treat these as inserted requirements even if an older task in `IMPLEMENTATION_PLAN.md` does not mention them explicitly:

### Before API implementation

- Verify `openapi` is implemented by Modelable.
- If missing, implement it upstream before continuing.
- Add OpenAPI generation and independent validation to `make generate`/`make acceptance`.

### During every product/conformance slice

- If a Modelable gap is found, stop adding downstream workaround code.
- Create the upstream failing test/fix first.
- Verify the upstream change using `MODELABLE_REF`.
- Resume the showcase implementation only after the generated behavior is correct.

### Capability coverage

OpenAPI MUST become a `product` capability once upstream reports it as implemented.

A newly discovered implemented target/capability MUST be covered rather than ignored. A newly required but missing general capability MUST be considered for upstream implementation rather than marked `excluded` merely to make CI green.

## 11. Acceptance additions

The final definition of done additionally requires:

1. OpenAPI is generated by Modelable, not handwritten or derived from the web/API framework.
2. The generated OpenAPI document passes an independent validator.
3. Running API contract tests prove the Axum implementation conforms to generated OpenAPI request/reply contracts.
4. OpenAPI generation is deterministic.
5. OpenAPI appears as an implemented capability/target in the tested Modelable version.
6. No permanent showcase patch layer exists for Modelable-generated artifacts.
7. Every general Modelable defect or missing capability encountered during implementation is either fixed upstream or explicitly documented as an intentional upstream limitation with a corresponding showcase boundary test.

The governing rule is:

> The showcase adapts to product-specific concerns. Modelable adapts when its general-purpose contract/compiler surface is insufficient. Never hide a Modelable gap inside the showcase.
