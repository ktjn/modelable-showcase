# Modelable Clinic — web

React + TypeScript + Vite frontend for the Modelable Clinic showcase product.

See `SPEC.md` §4.1 and `IMPLEMENTATION_PLAN.md` Phase 6/10 in the repository root for requirements. Consumes Modelable-generated TypeScript directly from `../../generated/typescript` via the `@generated` path alias (see `vite.config.ts` and `tsconfig.app.json`) — no generated files are copied or committed. Against the pinned `1.13.0`, UPSTREAM_FINDINGS.md #12/#13 (the two TypeScript-target compile-breaking bugs fixed in 1.8.0 that once forced a `src/generated-types.ts` workaround) remain fixed, so the app imports the real generated interfaces (e.g. `PatientPatientV2` from `@generated/patient.Patient.v2`) directly.

## Commands

Run from `apps/web/` after `make generate` has populated `../../generated/`:

```bash
npm ci
npm test -- --run   # Vitest unit tests
npm run build        # tsc -b && vite build
npm run dev           # local dev server
```
