import { Link } from 'react-router-dom'

export function Home() {
  return (
    <section className="hero">
      <h1>Modelable Clinic</h1>
      <p className="hero__lede">
        A small outpatient clinic product built to prove Modelable contracts end to end: patient → appointment →
        encounter → observation → invoice → payment → summary.
      </p>
      <div className="hero__links">
        <Link className="button button--primary" to="/patients">
          View patients
        </Link>
        <Link className="button" to="/schedule">
          Open schedule
        </Link>
      </div>
    </section>
  )
}
