import { NavLink, Route, Routes } from 'react-router-dom'
import { Analytics } from './pages/Analytics'
import { Home } from './pages/Home'
import { PatientCreate } from './pages/PatientCreate'
import { PatientDetail } from './pages/PatientDetail'
import { Patients } from './pages/Patients'
import { Schedule } from './pages/Schedule'

function App() {
  return (
    <div>
      <nav>
        <NavLink to="/" end>
          Home
        </NavLink>
        <NavLink to="/patients">Patients</NavLink>
        <NavLink to="/schedule">Schedule</NavLink>
        <NavLink to="/analytics">Analytics</NavLink>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/patients" element={<Patients />} />
          <Route path="/patients/new" element={<PatientCreate />} />
          <Route path="/patients/:id" element={<PatientDetail />} />
          <Route path="/schedule" element={<Schedule />} />
          <Route path="/analytics" element={<Analytics />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
