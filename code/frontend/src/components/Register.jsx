import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function Register({ user, onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  useEffect(() => { if (user) navigate('/') }, [user, navigate])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!username.trim() || !password) { setError('All fields are required.'); return }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    setBusy(true)
    try {
      await api.register(username.trim(), password)
      await onLogin(username.trim(), password)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <section className="card narrow">
      <h2>Create an account</h2>
      <form onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="username">Username <span className="req">*</span></label>
          <input id="username" value={username} autoComplete="username"
                 onChange={(e) => setUsername(e.target.value)} placeholder="3-50 letters, digits, _ . -" />
        </div>
        <div className="field">
          <label htmlFor="password">Password <span className="req">*</span></label>
          <input id="password" type="password" value={password}
                 onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" />
        </div>
        {error && <p className="err">{error}</p>}
        <button type="submit" className="submit-btn" disabled={busy}>
          {busy ? 'Creating...' : 'Sign up'}
        </button>
      </form>
      <p className="side-empty">Already have an account? <Link to="/login">Log in</Link></p>
    </section>
  )
}