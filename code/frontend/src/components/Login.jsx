import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Login({ user, onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  useEffect(() => { if (user) navigate('/') }, [user, navigate])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!username.trim() || !password) { setError('Username and password are required.'); return }
    setBusy(true)
    try { await onLogin(username.trim(), password) }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  return (
    <section className="card narrow">
      <h2>Log in</h2>
      <form onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="username">Username <span className="req">*</span></label>
          <input id="username" value={username} autoComplete="username"
                 onChange={(e) => setUsername(e.target.value)} placeholder="s3209_writer" />
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