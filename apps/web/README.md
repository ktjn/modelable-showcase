# Modelable Clinic — web

React + TypeScript + Vite frontend for the Modelable Clinic showcase product.

See `SPEC.md` §4.1 and `IMPLEMENTATION_PLAN.md` Phase 6/10 in the repository root for requirements. Consumes Modelable-generated TypeScript directly from `../../generated/typescript` via the `@generated` path alias (see `vite.config.ts` and `tsconfig.app.json`) — no generated files are copied or committed. See `src/generated-types.ts` for the current workaround around `UPSTREAM_FINDINGS.md` #12/#13 (two upstream TypeScript-target compile-breaking bugs).

## Commands

Run from `apps/web/` after `make generate` has populated `../../generated/`:

```bash
npm ci
npm test -- --run   # Vitest unit tests
npm run build        # tsc -b && vite build
npm run dev           # local dev server
```
