import { useEffect, useState } from 'react'
import { useDispatch } from 'react-redux'
import { Link, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { api } from './api'
import { clearTrials, fetchTrials } from './store/trialsSlice'
import { fetchSponsors } from './store/sponsorsSlice'
import Home from './components/Home.jsx'
import Login from './components/Login.jsx'
import CreateRecord from './components/CreateRecord.jsx'
import UpdateRecord from './components/UpdateRecord.jsx'
import Register from './components/Register.jsx'

function LoginRequired() {
  return (
    <section className="card narrow">
      <p className="state state-info">Login required</p>
      <p className="side-empty">Please <Link to="/login">log in</Link> to view and manage trial records.</p>
    </section>
  )
}

export default function App() {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(true)
  const dispatch = useDispatch()
  const navigate = useNavigate()

  // On page load: is there a valid session cookie?
  useEffect(() => {
    api.me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setChecking(false))
  }, [])

  // When the user logs in: load trials + sponsors into the Redux store
  useEffect(() => {
    if (!user) { dispatch(clearTrials()); return }
    dispatch(fetchTrials())
    dispatch(fetchSponsors())
  }, [user, dispatch])

  async function handleLogin(email, password) {
    setUser(await api.login(email, password))
  }

  async function handleLogout() {
    await api.logout().catch(() => {})
    setUser(null)
    navigate('/login')
  }

  const protect = (element) =>
    checking ? <p className="state state-loading">Checking session...</p>
      : user ? element : <LoginRequired />

  return (
    <>
      <div className="topbar"></div>
      <main className="wrap">
        <header className="page-head">
          <div className="reg-badge">TRIAL REGISTRY · s3209</div>
          <h1>Clinical Trial Listing</h1>
          <nav className="nav">
            <div className="nav-links">
              <NavLink to="/" end className="nav-link">Home</NavLink>
              {user && <NavLink to="/create" className="nav-link">Add Trial</NavLink>}
              {user && <NavLink to="/update" className="nav-link">Update Trial</NavLink>}
            </div>
            <div className="nav-links">
              {user ? (
                <>
                  <span className="nav-user">Signed in as <strong>{user.name}</strong></span>
                  <button className="btn-small" onClick={handleLogout}>Log out</button>
                </>
              ) : (
                <>
                  <NavLink to="/login" className="nav-link">Log in</NavLink>
                  <NavLink to="/register" className="nav-link">Sign up</NavLink>
                </>
              )}
            </div>
          </nav>
        </header>

        <Routes>
          <Route path="/" element={checking
            ? <p className="state state-loading">Checking session...</p>
            : <Home user={user} />} />
          <Route path="/login" element={<Login user={user} onLogin={handleLogin} />} />
          <Route path="/register" element={<Register user={user} onLogin={handleLogin} />} />
          <Route path="/create" element={protect(<CreateRecord />)} />
          <Route path="/update" element={protect(<UpdateRecord />)} />
        </Routes>
      </main>
    </>
  )
}
