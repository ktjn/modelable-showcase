# Modelable Showcase

Downstream product and acceptance suite for [Modelable](https://github.com/ktjn/modelable).

The showcase will build a small fictional outpatient-clinic product while exercising Modelable language features, generated targets, compatibility behavior, database DDL, downstream language compilation, LSP behavior, and edge cases.

All data is synthetic. This is a technical showcase, not clinical software.

## Start here

Read these in order before implementing anything:

1. [`SPEC.md`](SPEC.md) — authoritative product scope and acceptance contract.
2. [`UPSTREAM_POLICY.md`](UPSTREAM_POLICY.md) — mandatory upstream-first policy. This overrides conflicting shortcuts in the spec or plan.
3. [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) — task-by-task execution plan.
4. [`UPSTREAM_FINDINGS.md`](UPSTREAM_FINDINGS.md) — log of real Modelable behavior this showcase has found diverging from its own docs or crashing instead of diagnosing. Check it before re-discovering the same lexer error twice.

The implementation plan is intentionally explicit enough for small implementation agents: each slice defines files, constraints, tests, verification commands, and completion criteria.

## Non-negotiable rules

- OpenAPI MUST be generated directly by Modelable from `.mdl`; never maintain a handwritten or framework-derived canonical OpenAPI document.
- If the showcase exposes a general Modelable gap, fix Modelable upstream first instead of adding a permanent showcase workaround.
- Verify upstream fixes with `MODELABLE_REF=<branch-or-sha> make acceptance` before depending on them here.
- Current Modelable versions may not yet advertise an implemented OpenAPI emitter. If so, implementing that emitter upstream is a prerequisite for the stable HTTP API slice.

## Final target

When implemented, the repository must support:

```bash
docker compose up --build
make acceptance
MODELABLE_REF=main make acceptance
```

Generated artifacts remain disposable build output. `model/registry-ids.lock` is the intentional exception and is committed as stable Modelable semantic-ID allocation state.
