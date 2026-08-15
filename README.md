# Modelable Showcase

Downstream product and acceptance suite for [Modelable](https://github.com/ktjn/modelable).

The showcase will build a small fictional outpatient-clinic product while exercising Modelable language features, generated targets, compatibility behavior, database DDL, downstream language compilation, LSP behavior, and edge cases.

All data is synthetic. This is a technical showcase, not clinical software.

## Start here

1. Read [`SPEC.md`](SPEC.md) for the authoritative scope and acceptance contract.
2. Follow [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) task-by-task.

The implementation plan is intentionally explicit enough for small implementation agents: each slice defines files, constraints, tests, verification commands, and completion criteria.

## Final target

When implemented, the repository must support:

```bash
docker compose up --build
make acceptance
MODELABLE_REF=main make acceptance
```

Generated artifacts remain disposable build output. `model/registry-ids.lock` is the intentional exception and is committed as stable Modelable semantic-ID allocation state.
