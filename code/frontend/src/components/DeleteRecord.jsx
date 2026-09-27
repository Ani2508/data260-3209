import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

export default function DeleteRecord({ trials, onDelete }) {
  const [params] = useSearchParams()
  const id = Number(params.get('id'))
  const record = trials.find((t) => t.id === id)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  if (!record) {
    return (
      <section className="card narrow">
        <p className="state state-error">Trial not found. Choose "Delete" from the list.</p>
        <Link to="/">Back to list</Link>
      </section>
    )
  }

  async function handleDelete() {
    setBusy(true)
    try {
      await onDelete(id)
      navigate('/')
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <section className="card narrow">
      <h2>Delete Trial #{id}</h2>
      <div className="record-box">
        <p><strong>Trial Title:</strong> {record.trialTitle}</p>
        <p><strong>Sponsor:</strong> {record.sponsor}</p>
      </div>
      <p className="side-empty">This permanently removes the trial from the database.</p>
      {error && <p className="err">{error}</p>}
      <button className="submit-btn danger-btn" onClick={handleDelete} disabled={busy}>
        {busy ? 'Deleting...' : 'Delete Trial'}
      </button>
      <Link to="/" className="clear-btn cancel-link">Cancel</Link>
    </section>
  )
}