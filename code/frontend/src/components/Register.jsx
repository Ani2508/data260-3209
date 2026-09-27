import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function Register({ user, onLogin }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  useEffect(() => { if (user) navigate('/') }, [user, navigate])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!name.trim() || !email.trim() || !password) { setError('All fields are required.'); return }
    if (password.length < 6) { setError('Password must be at least 6 characters.'); return }
    setBusy(true)
    try {
      await api.register(name.trim(), email.trim(), password)
      await onLogin(email.trim(), password)
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
          <label htmlFor="name">Name <span className="req">*</span></label>
          <input id="name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="email">Email <span className="req">*</span></label>
          <input id="email" type="email" value={email}
                 onChange={(e) => setEmail(e.target.value)} placeholder="you@sjsu.edu" />
        </div>
        <div className="field">
          <label htmlFor="password">Password <span className="req">*</span></label>
          <input id="password" type="password" value={password}
                 onChange={(e) => setPassword(e.target.value)} placeholder="At least 6 characters" />
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