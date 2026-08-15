// Re-exports Modelable-generated TypeScript types for consumption by the
// rest of the app (SPEC.md Sec 4.1: "MUST consume Modelable-generated
// TypeScript types for API contracts... MUST NOT define parallel
// handwritten interfaces"). Sourced directly from generated/typescript/
// via the @generated path alias (tsconfig.app.json / vite.config.ts) - no
// generated files are copied or committed.
//
// Only patient.ContactDetails.v0.ts and patient.Address.v0.ts are
// imported here, not patient.Patient.v2.ts (the actual Patient entity)
// or any *.PatientDb/*.PatientRequest/*.PatientReply/*.PatientEvent
// projection. Two real, upstream compile-breaking bugs in
// `compile --target typescript` (UPSTREAM_FINDINGS.md #12 and #13) mean
// every one of those files references an undefined type name and fails
// `tsc --noEmit --strict` - #12: semantic-typed fields (e.g. Patient's
// own `patientId: PatientId`) never get an import anywhere in this
// target; #13: every projection-kind file (Db/Request/Reply/Event) never
// emits any imports at all, even for value types that import correctly
// on entity files. ContactDetails and Address are plain `value` types
// with no semantic-typed or cross-file fields, so they're unaffected by
// either bug and compile as-is - they're still real generated Patient
// domain data (Patient.contact/Patient.address), just not the top-level
// Patient interface itself.
//
// Revisit once Modelable is re-pinned past a release that fixes #12/#13
// (tracked as a separate task per project owner direction, not blocking
// this one) - Patient itself should become importable at that point.
export type { ContactDetails } from '@generated/patient.ContactDetails.v0'
export type { Address } from '@generated/patient.Address.v0'
