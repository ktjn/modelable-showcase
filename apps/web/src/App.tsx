import { NavLink, Route, Routes } from 'react-router-dom'
import { Analytics } from './pages/Analytics'
import { Home } from './pages/Home'
import { PatientCreate } from './pages/PatientCreate'
import { PatientDetail } from './pages/PatientDetail'
import { Patients } from './pages/Patients'
import { Schedule } from './pages/Schedule'

function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__inner">
          <span className="brand" aria-hidden="true">
            <span className="brand__mark">M</span>
            Modelable Clinic
          </span>
          <nav>
            <NavLink to="/" end>
              Home
            </NavLink>
            <NavLink to="/patients">Patients</NavLink>
            <NavLink to="/schedule">Schedule</NavLink>
            <NavLink to="/analytics">Analytics</NavLink>
          </nav>
        </div>
      </header>
      <main>
        <div className="page">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/patients" element={<Patients />} />
            <Route path="/patients/new" element={<PatientCreate />} />
            <Route path="/patients/:id" element={<PatientDetail />} />
            <Route path="/schedule" element={<Schedule />} />
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}

export default App
