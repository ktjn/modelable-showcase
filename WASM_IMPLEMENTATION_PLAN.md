# Modelable Showcase — WASM Implementation Plan

**Status:** implementation plan  
**Repository:** `ktjn/modelable-showcase`  
**Scope:** convert the current Modelable Clinic product so it can run entirely in the browser from GitHub Pages, while preserving the existing full-stack runtime.

## 1. Goal

Add a second runtime for the existing showcase:

```text
Full-stack mode
React/Vite -> HTTP -> Rust/Axum -> PostgreSQL + ClickHouse

WASM mode
React/Vite -> browser runtime -> Rust/WASM -> browser persistence
```

The WASM mode must run from static files only. It must require no server process, database, container, secret, external SaaS dependency, or network service after the page assets are loaded.

The purpose is not merely to make the UI deployable. The purpose is to prove that Modelable-generated Rust contracts and the current clinic application semantics can execute in a browser-hosted WebAssembly runtime.

The existing full-stack mode remains required because it proves generated SQL, PostgreSQL, ClickHouse, Axum integration, and real infrastructure boundaries. WASM mode is an additional product/conformance path, not a replacement.

## 2. Design principles

1. Preserve the current clinic behavior and routes conceptually. Do not build a separate toy demo.
2. Keep Modelable-generated contracts as the domain/API source of truth.
3. Do not duplicate generated domain types in handwritten Rust or TypeScript.
4. Separate domain/application behavior from HTTP, SQLx, ClickHouse, Tokio, environment variables, and process-level concerns.
5. Compile the portable Rust layer with `wasm32-unknown-unknown` in CI.
6. Keep browser-specific persistence outside the reusable domain layer.
7. Keep the first WASM runtime simple. Do not introduce WASI, the Component Model, WIT, SQLite, service workers, or multi-language execution until the current Rust product works end to end.
8. Keep the browser runtime deterministic and resettable so it is useful as a showcase and acceptance harness.
9. Treat WASM compile failures in generated Modelable Rust as upstream Modelable findings, not as permanent local generated-code rewrites.
10. Preserve equivalent observable product behavior between HTTP mode and WASM mode where infrastructure semantics do not intentionally differ.

## 3. Current constraints

The current web app is already suitable for static hosting except for its backend dependency. All backend access is funneled through the small `apps/web/src/api` layer and ultimately the HTTP client.

The current Rust application is not directly WASM-compatible because `apps/api` combines several concerns:

- Axum routing and HTTP status handling;
- Tokio runtime assumptions;
- SQLx/PostgreSQL persistence;
- ClickHouse analytics writes/queries;
- environment-based runtime configuration;
- generated Modelable Rust contracts;
- application rules such as appointment overlap validation, state transitions, mapping, summaries, and billing behavior.

The first architectural task is therefore extraction, not compilation.

## 4. Target architecture

Target repository shape:

```text
apps/
  web/
  api/

crates/
  showcase-core/
  showcase-store-memory/
  showcase-wasm/
```

Do not create more crates unless implementation pressure clearly justifies them.

Target dependency direction:

```text
                          generated Modelable Rust
                                   ^
                                   |
                            showcase-core
                           /             \
                          /               \
                apps/api                  showcase-wasm
             Axum + SQLx + CH              wasm-bindgen
                    |                           |
       PostgreSQL + ClickHouse          browser runtime
                                              |
                                      IndexedDB adapter
```

`showcase-core` must not depend on Axum, SQLx, ClickHouse, Tokio, browser APIs, `wasm-bindgen`, or JavaScript types.

The full-stack and WASM runtimes must invoke the same core application operations wherever practical.

## 5. Runtime boundary

Do not expose every Rust function individually through `wasm-bindgen`.

Use a compact request/response boundary that is easy to keep stable and later reuse for other language runtimes.

Initial conceptual interface:

```text
initialize(snapshot?) -> RuntimeInfo
execute(command) -> CommandResult
query(query) -> QueryResult
snapshot() -> Snapshot
reset() -> RuntimeInfo
seed() -> RuntimeInfo
```

The boundary payloads should use Modelable-generated request/reply/event structures where they already represent the contract. A thin tagged envelope may be handwritten for dispatch.

Example conceptual request:

```json
{
  "type": "CreatePatient",
  "payload": {
    "patientId": "...",
    "legalName": "..."
  }
}
```

Example conceptual response:

```json
{
  "ok": true,
  "result": { }
}
```

Errors must be normalized into a stable application error shape rather than leaking Rust panic strings or JavaScript exceptions.

Suggested error categories:

```text
bad_request
not_found
conflict
validation
internal
```

Keep HTTP status mapping in `apps/api`. The core should return semantic error categories. The WASM runtime should surface those categories directly to TypeScript.

## 6. State model

### 6.1 First implementation

Use a serializable in-memory state owned by the Rust WASM runtime.

Suggested shape:

```text
ClinicState
  patients
  appointments
  encounters
  observations
  invoices
  payments
  analytics events / derived counters as needed
```

The state should store Modelable-generated DB/domain representations where practical rather than introducing parallel handwritten entities.

Use keyed collections appropriate to the current access patterns. Prefer simple maps/vectors over reproducing PostgreSQL indexing internals.

### 6.2 Persistence

Persist a serialized snapshot in IndexedDB from TypeScript.

Initial flow:

```text
page load
  -> IndexedDB.get(snapshot)
  -> WASM initialize(snapshot)

mutating command
  -> WASM execute(command)
  -> WASM snapshot()
  -> IndexedDB.put(snapshot)
```

This deliberately keeps browser APIs out of Rust.

Do not use `localStorage` as the canonical persistence layer. It is synchronous, size-limited, and provides little value over IndexedDB.

Do not add SQLite/OPFS in the first milestone. The showcase data volume does not justify it and it would obscure the actual Modelable/WASM proof.

### 6.3 Snapshot format

The snapshot is a browser runtime implementation detail, but it must be versioned.

Minimum envelope:

```json
{
  "formatVersion": 1,
  "modelableVersion": "...",
  "schemaIdentity": "...",
  "state": { }
}
```

Use available generated schema/version/content-signature metadata for `schemaIdentity` where possible.

On incompatible snapshot format/schema identity:

- never silently reinterpret data;
- fail with a clear incompatibility reason;
- allow the UI to reset the synthetic sandbox;
- migration support can be added later as a showcase scenario.

## 7. Analytics behavior

ClickHouse cannot exist in the pure static runtime. Do not emulate ClickHouse itself.

Instead separate analytics semantics from the ClickHouse adapter.

Target:

```text
core operation
  -> domain state mutation
  -> analytics/event record

full-stack adapter
  -> persist analytics/event record to ClickHouse

WASM runtime
  -> retain analytics/event record in browser state
  -> compute current analytics queries locally
```

The WASM analytics page should preserve the same user-visible figures as the current product for the same command sequence.

This proves generated event/data shapes and application semantics. The existing full-stack path remains the proof for generated ClickHouse DDL and ClickHouse integration.

## 8. HTTP compatibility strategy

Do not rewrite every page immediately.

Introduce a runtime-neutral TypeScript client interface behind the existing `apps/web/src/api` modules.

Target concept:

```ts
interface ShowcaseRuntime {
  get<T>(path: string): Promise<T>
  post<T>(path: string, body: unknown): Promise<T>
  patch<T>(path: string, body: unknown): Promise<T>
}
```

Implement:

```text
HttpRuntime
WasmRuntime
```

The existing domain-specific modules (`patients.ts`, `appointments.ts`, `encounters.ts`, `billing.ts`, `summary.ts`, `analytics.ts`) should continue to expose their current functions.

They should depend on the runtime abstraction instead of importing `fetch` directly.

For the first migration, preserving the existing route-like `path + method + body` contract is preferred because it minimizes frontend churn and provides a direct behavior parity surface.

The WASM adapter may internally dispatch route-like calls to typed WASM commands. Do not implement a fake HTTP server inside WASM.

Later, once parity is proven, the frontend API can move to explicit command/query operations if that materially improves type safety.

## 9. Execution isolation

Run the WASM runtime in a Web Worker.

Reasons:

- avoid blocking React rendering;
- provide a clean runtime/process-like boundary;
- make later multi-language workers straightforward;
- isolate panics/runtime failures from UI logic;
- provide one message protocol that can later host Rust, Python, C#, Java, and other runtimes.

Worker shape:

```text
apps/web/src/runtime/
  runtime.ts
  http-runtime.ts
  wasm-runtime.ts
  wasm-worker.ts
  protocol.ts
  persistence.ts
```

The main thread should not directly manipulate Rust WASM state.

Message protocol should include request IDs so concurrent React Query calls can be correlated safely.

## 10. Detailed implementation slices

Implement in order. Each slice must leave the current full-stack mode working.

### Slice 0 — Record the architecture decision

Update `SPEC.md` before product code so the authoritative specification recognizes two runtime modes.

Change the runtime architecture section to state:

- full-stack mode remains the infrastructure acceptance path;
- browser/WASM mode is a static runtime acceptance path;
- both run the same clinic product;
- WASM mode may replace infrastructure persistence/analytics with browser adapters while preserving observable semantics;
- GitHub Pages deployment is a required WASM acceptance target once this plan lands.

Update `README.md` with a short future/current runtime description and link to this plan.

Do not weaken existing PostgreSQL/ClickHouse acceptance requirements.

Acceptance:

```text
SPEC.md describes both modes without contradicting existing infrastructure gates.
README links to WASM_IMPLEMENTATION_PLAN.md.
```

### Slice 1 — Add WASM compatibility probe for generated Rust

Before refactoring application code, prove which generated Modelable Rust packages compile for the browser target.

Add a script/Make target equivalent to:

```bash
rustup target add wasm32-unknown-unknown
modelable compile ... --target rust ...
cargo check --target wasm32-unknown-unknown <generated package(s)>
```

If generated packages are independent Cargo packages, check every package consumed by the clinic product.

Capture any failures in `UPSTREAM_FINDINGS.md` with minimal generated reproduction and classify whether the issue is:

- generated code uses a platform-specific dependency;
- a generated primitive mapping is not WASM-safe;
- Cargo features pull OS-specific code;
- generated metadata/build scripts assume a native host;
- showcase code, not Modelable output, caused the failure.

Do not patch generated output after generation.

Add this check to CI as a separate job once it is stable.

Acceptance:

```bash
make wasm-check-generated
```

must either pass or point to an explicitly tracked upstream blocker. The next slices should not proceed by hiding a generated-code incompatibility.

### Slice 2 — Create `showcase-core`

Create:

```text
crates/showcase-core/Cargo.toml
crates/showcase-core/src/lib.rs
```

Dependencies should be limited to:

- generated Rust contracts;
- Serde/serde_json if required;
- UUID/chrono only with WASM-compatible features;
- small platform-neutral utilities.

Do not add Axum, Tokio, SQLx, ClickHouse, wasm-bindgen, web-sys, js-sys, or storage libraries.

Move pure behavior from `apps/api` incrementally.

Good first candidates:

- request -> DB/domain mappings;
- DB/domain -> reply mappings;
- enum mapping;
- slot validation;
- overlap calculation;
- state-transition validation;
- invoice/payment arithmetic;
- summary assembly that does not inherently require SQL.

Do not move `PgRow` decoding, SQL strings, Axum extractors, HTTP status conversion, DB pools, or ClickHouse clients.

Define semantic `ShowcaseError` in core.

Acceptance:

```bash
cargo test --manifest-path crates/showcase-core/Cargo.toml
cargo check --target wasm32-unknown-unknown --manifest-path crates/showcase-core/Cargo.toml
```

### Slice 3 — Introduce repository/application ports

Define only the ports needed to decouple core use cases from storage.

Prefer capability-oriented interfaces over one generic database abstraction.

Possible shape:

```text
PatientStore
AppointmentStore
ClinicalStore
BillingStore
AnalyticsStore
```

But avoid unnecessary async abstraction initially.

Because browser state is in-memory inside the WASM worker, a simpler approach may be better:

```text
ClinicEngine {
  state: ClinicState
}
```

and use pure operations directly against state.

Then make the native API adapt database rows into core operations where appropriate.

Choose the smallest design that avoids duplicating business rules. Do not introduce traits merely to imitate SQL repositories.

Decision rule:

- if logic needs atomic DB behavior in native mode, keep persistence orchestration in the API adapter and call shared core validation/mapping;
- if logic is deterministic over domain values, move it into core;
- if the exact same application workflow can reasonably operate over `ClinicState`, implement it once in core.

Document any rule that intentionally remains duplicated because native transactional semantics are materially different.

### Slice 4 — Implement in-memory clinic engine

Add a `ClinicEngine` or equivalent in `showcase-core`.

Implement the currently exposed product flows:

1. create/search/get patient;
2. create/reschedule/cancel appointment;
3. daily schedule;
4. patient appointments;
5. create/start/complete encounter as supported by current API;
6. record/list observations;
7. create invoice;
8. record payment;
9. patient summary;
10. analytics queries.

Preserve current behavior for:

- duplicate IDs;
- malformed IDs;
- appointment overlap;
- cancelled appointment restrictions;
- encounter state transitions;
- invoice/payment constraints;
- not-found behavior;
- generated enum serialization;
- timestamps/server-generated fields.

Inject time instead of calling platform clock directly inside business operations.

Suggested core boundary:

```text
Clock::now()
```

For the initial implementation this may simply be a timestamp passed into mutating commands. This also makes deterministic tests easier.

Write core behavioral tests using the same synthetic workflows as API tests.

### Slice 5 — Add snapshot serialization

Make `ClinicState` serializable/deserializable.

Add:

```text
SnapshotEnvelope
snapshot()
restore(snapshot)
reset()
seed()
```

Use generated Rust types directly in snapshots where they already derive Serde.

Add tests for:

- empty round trip;
- populated round trip;
- deterministic semantic equality after restore;
- incompatible format version;
- incompatible schema identity;
- corrupt JSON;
- seed -> snapshot -> restore -> queries produce equal results.

Byte-identical JSON is not required unless canonical serialization is deliberately implemented. Semantic state equality is sufficient.

### Slice 6 — Create `showcase-wasm`

Create:

```text
crates/showcase-wasm/Cargo.toml
crates/showcase-wasm/src/lib.rs
```

Use `wasm-bindgen` as a thin transport layer only.

Export the compact runtime interface described earlier.

Do not expose generated structs one by one through generated/manual bindgen glue.

Preferred transport:

```text
JSON string or serde-compatible JsValue envelope
```

Choose the simpler mechanism after measuring toolchain friction. JSON string transport is acceptable initially because correctness and portability matter more than micro-optimization for this showcase.

The crate must compile with:

```bash
cargo build --release --target wasm32-unknown-unknown
```

Package with the smallest standard tool that works cleanly with Vite, such as `wasm-bindgen-cli` or `wasm-pack`. Pin the chosen tool version in the repository bootstrap/tooling path.

### Slice 7 — Build the worker runtime

Add TypeScript worker infrastructure.

Requirements:

- lazy-load WASM once;
- initialize from a supplied snapshot;
- process multiple requests using request IDs;
- serialize errors into the common runtime error shape;
- never call DOM APIs from the worker;
- snapshot after successful mutating operations;
- expose explicit reset and seed commands.

Do not persist after read-only queries.

Worker startup failure must produce an actionable error in the UI, not an infinite loading state.

### Slice 8 — Add IndexedDB persistence

Implement a tiny persistence module in TypeScript using native IndexedDB APIs or one small, well-maintained wrapper if native code becomes disproportionately complex.

Store only what is necessary:

```text
key: clinic-state
value: SnapshotEnvelope
```

No generic ORM.

Required behavior:

- first visit starts empty;
- successful mutation persists;
- reload restores;
- reset clears storage;
- seeded demo state persists;
- corrupt/incompatible snapshot offers reset instead of crashing the application.

Keep all data synthetic.

### Slice 9 — Add runtime-neutral frontend client

Refactor the current HTTP client behind `ShowcaseRuntime`.

Environment/build selection:

```text
VITE_SHOWCASE_RUNTIME=http
VITE_SHOWCASE_RUNTIME=wasm
```

Defaults:

- local current full-stack developer flow may remain `http`;
- GitHub Pages build must force `wasm`.

Do not let arbitrary query parameters select remote HTTP origins in the public Pages deployment.

`HttpRuntime` should preserve current fetch behavior.

`WasmRuntime` should talk only to the worker.

The existing domain-specific API modules should require minimal or no signature changes.

Add unit tests that run the same module-level request expectations against both runtime implementations where practical.

### Slice 10 — Route-parity adapter

Implement the route-like dispatch expected by current frontend modules.

Map existing operations, for example:

```text
POST  /api/patients
GET   /api/patients
GET   /api/patients/{id}
POST  /api/appointments
PATCH /api/appointments/{id}
POST  /api/appointments/{id}/cancel
GET   /api/schedule
...
```

Do not parse arbitrary URLs with a full routing library. A small explicit dispatch table is preferred.

Preserve query parameters used by patient search, schedules, and analytics.

Normalize WASM errors so frontend behavior matches HTTP mode semantically.

### Slice 11 — End-to-end browser parity

Create a WASM-specific Playwright project or test configuration.

Run the existing happy-path clinic journey against WASM mode:

```text
patient
-> appointment
-> encounter
-> observation
-> invoice
-> payment
-> summary
```

Add tests for:

- reload preserves state;
- reset clears state;
- seed produces useful demo data;
- appointment conflict behavior;
- patient search;
- analytics values;
- direct navigation/reload under the GitHub Pages base path.

Reuse existing E2E test helpers where possible. Avoid a parallel test suite containing copied workflows.

### Slice 12 — GitHub Pages build

Configure Vite for the repository base path.

Expected production base:

```text
/modelable-showcase/
```

Ensure all of these resolve under the base path:

- JS chunks;
- worker bundle;
- `.wasm` file;
- CSS/assets;
- SPA routes.

Prefer hash routing or a GitHub Pages-compatible SPA fallback strategy if BrowserRouter direct navigation cannot be made reliable with static hosting. Preserve normal URLs if a simple `404.html` SPA redirect works reliably.

Do not add a backend solely for route fallback.

Build command must produce a self-contained static artifact.

Suggested target:

```bash
make wasm-build
```

Output should be under the normal Vite `dist/` path and remain disposable.

### Slice 13 — GitHub Pages workflow

Add a dedicated deployment workflow using official GitHub Pages actions.

Trigger:

- push to `main` after CI success, or
- a reusable/dependent workflow if that better matches current CI structure;
- `workflow_dispatch` is useful for manual verification.

Workflow stages:

```text
checkout
install pinned Modelable
install Rust target/tooling
install Node dependencies
modelable generate
build WASM
build Vite with wasm runtime
run static/WASM smoke tests
upload Pages artifact
deploy Pages
```

Use minimum required permissions:

```text
contents: read
pages: write
id-token: write
```

No repository secrets should be required.

### Slice 14 — CI gates

Add explicit gates:

```text
wasm-generated
wasm-core
wasm-build
wasm-e2e
```

At minimum CI must prove:

```bash
cargo check --target wasm32-unknown-unknown <generated Rust packages>
cargo test showcase-core
cargo check --target wasm32-unknown-unknown showcase-core
cargo build --target wasm32-unknown-unknown showcase-wasm
npm run build in wasm mode
Playwright happy path in wasm mode
```

Do not remove existing native/API/database gates.

The repository should now prove both:

```text
native generated Rust -> Axum/DB product
browser generated Rust -> WASM product
```

### Slice 15 — Runtime parity tests

Create a small set of reusable scenario vectors at the application-operation level.

Each vector should describe commands and expected observable results, not implementation details.

Example:

```json
{
  "name": "appointment overlap",
  "commands": [ ... ],
  "expect": {
    "lastError": "conflict"
  }
}
```

Run vectors against:

- `ClinicEngine` directly;
- native HTTP API where practical;
- WASM worker runtime.

Prioritize behaviors most likely to drift:

- generated enum mapping;
- date/time/duration serialization;
- null/optional handling;
- duplicate identity handling;
- state transitions;
- summary projection values;
- decimal/money behavior;
- analytics values.

Do not require equality of infrastructure-only metadata such as HTTP status text, database row ordering unless API semantics define it, or readiness endpoints.

### Slice 16 — Showcase visibility

Expose the runtime identity in the UI in a small non-intrusive location.

Example:

```text
Runtime: Rust / WebAssembly
Modelable: 1.x.y
Schema: <short identity>
Storage: IndexedDB
```

In HTTP mode show the corresponding native runtime identity.

Add buttons in WASM mode for:

```text
Seed demo data
Reset sandbox
Export snapshot
Import snapshot
```

Export/import can be added after persistence is stable but should be included before declaring the public sandbox complete. It makes the static showcase easier to inspect and reproduce without a backend.

Never imply that browser data is production-grade clinical storage.

## 11. Native API refactoring guidance

Avoid a big-bang rewrite of `apps/api`.

For each API module:

1. identify pure behavior;
2. move it to `showcase-core`;
3. add core tests;
4. make current Axum handler call it;
5. verify existing API tests;
6. implement equivalent `ClinicEngine` operation;
7. verify WASM parity.

Suggested order:

```text
patient
scheduling
clinical
billing
summary
analytics
```

Patient is simplest and proves generated model serialization.

Scheduling should follow early because overlap/state rules prove that real behavior has moved rather than only CRUD.

Analytics should be last because its persistence model intentionally differs most between runtimes.

## 12. Expected WASM blockers and mitigation

### Generated Rust platform assumptions

Risk: generated packages may enable dependencies/features that do not support `wasm32-unknown-unknown`.

Mitigation:

- add generated WASM compile gate first;
- fix Modelable upstream when the generated target is unnecessarily platform-specific;
- avoid local post-generation rewriting.

### `chrono`

Risk: clock/timezone features can pull platform behavior.

Mitigation:

- generated date/time value representation is fine if serialization compiles;
- inject current time from JS or a WASM-compatible clock boundary;
- avoid local timezone dependencies.

### `uuid`

Risk: random UUID generation may require browser entropy features.

Mitigation:

- prefer IDs supplied by the web app where current contracts already do so;
- if Rust must generate UUIDs, enable the browser-compatible random source explicitly;
- keep generation semantics aligned with Modelable requirements.

### Decimal behavior

Risk: generated decimal implementation may behave differently or use incompatible dependencies.

Mitigation:

- add explicit money round-trip/parity tests;
- treat generator/runtime incompatibility as an upstream finding.

### WASM bundle size

Risk: generated contracts and runtime can create a large download.

Mitigation:

- measure release artifact size;
- use release builds and standard WASM optimization if reproducible;
- do not compromise semantic coverage merely to hit an arbitrary size target;
- lazy-load the worker/WASM bundle if startup becomes materially affected.

### Browser storage evolution

Risk: Modelable schema changes make old IndexedDB snapshots unreadable.

Mitigation:

- version snapshot envelope from day one;
- include schema identity;
- fail closed and offer reset initially;
- later use this as a real schema-migration showcase feature.

### SPA routing on GitHub Pages

Risk: direct navigation to nested routes returns GitHub Pages 404.

Mitigation:

- test deployed-base direct navigation in Playwright/static server simulation;
- use a simple Pages-compatible fallback or hash routing rather than server assumptions.

## 13. Security and isolation

The public static sandbox must have no secrets and no privileged backend.

Rules:

- no API tokens in Vite environment variables;
- no external database URLs;
- no hidden production endpoints;
- no real patient/medical data;
- imported snapshot data remains local to the browser unless the user explicitly exports it;
- validate imported snapshot structure before handing it to core;
- bound snapshot size to prevent accidental browser memory exhaustion;
- worker messages must validate operation/envelope type rather than dynamically evaluating code;
- never use `eval`, dynamic module URLs from user input, or arbitrary fetch-based plugin loading.

GitHub Pages CSP control is limited compared with a normal server. Keep the application dependency surface small and avoid runtime-loaded third-party scripts.

## 14. Tooling additions

Expected additions:

```text
Rust target: wasm32-unknown-unknown
wasm-bindgen-cli or wasm-pack
Web Worker build through Vite
GitHub Pages Actions
```

Prefer existing repository bootstrap conventions for version pinning.

Do not require globally installed ad-hoc tools that CI does not also install explicitly.

Add Make targets with stable names:

```text
wasm-check-generated
wasm-build
wasm-test
wasm-e2e
pages-build
```

`make acceptance` should eventually include WASM compile/build/parity gates once the feature is complete and no longer experimental.

## 15. Definition of done for the first WASM milestone

The milestone is complete when all of the following are true:

1. Current generated Rust packages used by the clinic compile for `wasm32-unknown-unknown`.
2. A platform-neutral `showcase-core` owns the portable clinic behavior used by WASM.
3. The current full-stack product still passes its native/API/database acceptance tests.
4. A Rust WASM runtime executes the clinic product entirely in the browser.
5. The React application can switch between HTTP and WASM runtimes without separate page implementations.
6. WASM mode supports the complete existing happy-path clinic journey.
7. WASM state survives browser reload through IndexedDB.
8. The sandbox can be reset and seeded deterministically.
9. Analytics pages work without ClickHouse and produce equivalent values for equivalent browser state.
10. GitHub Pages serves the application correctly from `/modelable-showcase/`, including workers, WASM assets, and direct SPA navigation strategy.
11. No runtime backend or secret is required by the Pages deployment.
12. CI compiles generated Rust and core Rust for the WASM target.
13. Playwright executes the main product journey in WASM mode.
14. Representative parity scenarios produce equivalent semantic results between the native and WASM runtimes.
15. README documents both runtime modes and links to the public Pages sandbox.
16. Any Modelable generator changes required for WASM support are fixed upstream and covered by this downstream acceptance suite.

## 16. Explicit non-goals for this milestone

Do not include these in the first conversion:

- Python/Pyodide runtime;
- C#/.NET WASM runtime;
- Java/TeaVM runtime;
- Kotlin/Wasm runtime;
- Go/TinyGo runtime;
- cross-language differential execution;
- WIT/Component Model ABI;
- WASI server emulation;
- browser PostgreSQL/ClickHouse emulation;
- SQLite/OPFS unless simple IndexedDB proves insufficient;
- running Axum itself inside the browser;
- compiling Modelable itself in the browser;
- editing `.mdl` source inside the sandbox;
- dynamically regenerating contracts in the browser.

Those become follow-up milestones after the Rust WASM path establishes the common worker/runtime protocol.

## 17. Follow-up milestone: cross-language execution

Design this first implementation so the worker protocol can later host additional runtimes.

Future shape:

```text
React showcase
  |
  +-- TypeScript runtime worker
  +-- Rust WASM worker
  +-- Python/Pyodide worker
  +-- C#/.NET WASM worker
  +-- Java/Kotlin/Go/etc workers
```

The later cross-language milestone should feed identical Modelable-generated conformance vectors to every runtime and compare normalized results.

Do not implement this now, but avoid Rust-specific assumptions in the TypeScript worker protocol that would force it to be redesigned later.

## 18. Recommended commit slicing

Suggested commits:

```text
docs: define browser wasm runtime
ci: add generated rust wasm compatibility gate
refactor(core): extract portable patient behavior
refactor(core): extract scheduling behavior
refactor(core): extract clinical behavior
refactor(core): extract billing and summary behavior
feat(core): add in-memory clinic engine
feat(core): add versioned snapshot format
feat(wasm): expose clinic engine through wasm-bindgen
feat(web): add runtime abstraction
feat(web): add wasm worker runtime
feat(web): persist wasm state in indexeddb
test: run clinic e2e against wasm runtime
feat(web): add sandbox seed reset and snapshot controls
ci: build and test wasm showcase
ci: deploy wasm showcase to github pages
test: add native wasm parity scenarios
```

Keep each commit independently buildable where practical.

## 19. First implementation task

Start with the generated-code probe, not with frontend changes.

The first code change after the specification update should answer this question definitively:

> Can every generated Rust package currently consumed by Modelable Clinic compile unchanged for `wasm32-unknown-unknown`?

That result determines whether the next work is purely showcase refactoring or whether Modelable itself needs a WASM portability fix first.
