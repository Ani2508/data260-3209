import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Login({ user, onLogin }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  useEffect(() => { if (user) navigate('/') }, [user, navigate])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!email.trim() || !password) { setError('Email and password are required.'); return }
    setBusy(true)
    try { await onLogin(email.trim(), password) }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  return (
    <section className="card narrow">
      <h2>Log in</h2>
      <form onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="email">Email <span className="req">*</span></label>
          <input id="email" type="email" value={email}
                 onChange={(e) => setEmail(e.target.value)} placeholder="you@sjsu.edu" />
        </div>
        <div className="field">
          <label htmlFor="password">Password <span className="req">*</span></label>
          <input id="password" type="password" value={password}
                 onChange={(e) => setPassword(e.target.value)} />
        </div>
        {error && <p className="err">{error}</p>}
        <button type="submit" className="submit-btn" disabled={busy}>
          {busy ? 'Logging in...' : 'Log in'}
        </button>
      </form>
    </section>
  )
}