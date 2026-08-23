import { Link } from 'react-router-dom'
import { runtime } from '../api/client'

const DEMO_PATIENT_ID = '9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d'

const FEATURES = [
  {
    label: 'Model',
    title: 'One versioned source',
    copy: 'Patient, scheduling, clinical, and billing contracts begin as domain-owned .mdl definitions.',
  },
  {
    label: 'Generate',
    title: 'Every consuming surface',
    copy: 'The compiler emits typed Rust and TypeScript, SQL, OpenAPI, Protobuf/gRPC, governance metadata, and more.',
  },
  {
    label: 'Run',
    title: 'Two real runtimes',
    copy: 'Use Axum with PostgreSQL and ClickHouse, or run the same clinic behavior locally in Rust WebAssembly.',
  },
  {
    label: 'Prove',
    title: 'Contracts under load',
    copy: 'Compatibility, deterministic output, downstream compilers, real databases, parity vectors, and browser journeys all gate changes.',
  },
]

export function Home() {
  const browserSandbox = runtime.kind === 'wasm'

  return (
    <>
      <section className="hero">
        <span className="hero__eyebrow">.mdl → contracts → running product</span>
        <h1>Modelable Clinic</h1>
        <p className="hero__lede">
          Follow one fictional clinic journey from patient registration through appointment, encounter, observation,
          invoice, payment, and summary. Every surface starts from the same versioned Modelable contracts.
        </p>
        <div className="hero__links">
          <Link className="button button--primary" to={browserSandbox ? `/patients/${DEMO_PATIENT_ID}` : '/patients'}>
            {browserSandbox ? 'Explore Ada’s record' : 'View patients'}
          </Link>
          <a className="button" href="https://ktjn.github.io/modelable/">
            Read Modelable docs
          </a>
        </div>
      </section>

      <section className="feature-tour" aria-labelledby="feature-tour-title">
        <div className="section-heading">
          <span className="section-heading__kicker">What this proves</span>
          <h2 id="feature-tour-title">A contract’s path through a working system</h2>
        </div>
        <ol className="feature-trail">
          {FEATURES.map(feature => (
            <li key={feature.label}>
              <span className="feature-trail__label">{feature.label}</span>
              <strong>{feature.title}</strong>
              <p>{feature.copy}</p>
            </li>
          ))}
        </ol>
        <div className="docs-links" aria-label="Modelable documentation">
          <a href="https://ktjn.github.io/modelable/getting-started/">Getting started</a>
          <a href="https://ktjn.github.io/modelable/language-reference/">Language reference</a>
          <a href="https://github.com/ktjn/modelable-showcase/tree/main/model">View the clinic models</a>
        </div>
      </section>

      <section className="demo-record" aria-labelledby="demo-record-title">
        <div>
          <span className="section-heading__kicker">Fictional sample record</span>
          <h2 id="demo-record-title">Ada’s clinic journey is ready to inspect</h2>
          <p>
            The browser sandbox starts with one deterministic patient, a completed encounter and observation,
            a SEK 125.00 invoice, and a SEK 75.00 payment. It stays entirely in this browser.
          </p>
        </div>
        <dl className="demo-record__facts">
          <div><dt>Patient</dt><dd>Ada Lovelace</dd></div>
          <div><dt>Appointment</dt><dd>1 Sep 2026 · 09:00</dd></div>
          <div><dt>Observation</dt><dd>36.8 °C · normal</dd></div>
          <div><dt>Invoice</dt><dd>SEK 125.00 · 75.00 paid</dd></div>
        </dl>
        <div className="demo-record__links">
          {browserSandbox && <Link to={`/patients/${DEMO_PATIENT_ID}`}>Open patient summary</Link>}
          <Link to="/schedule">See the schedule</Link>
          <Link to="/analytics">View clinic analytics</Link>
        </div>
      </section>
    </>
  )
}
