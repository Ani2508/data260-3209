import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function CreateRecord({ onAdd }) {
  const [trialTitle, setTrialTitle] = useState('')
  const [sponsor, setSponsor] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    const title = trialTitle.trim()
    const spon = sponsor.trim()
    if (!title || !spon) { setError('Both fields are required.'); return }
    setBusy(true)
    try {
      await onAdd({ trialTitle: title, sponsor: spon })
      navigate('/') // back to the updated list
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <section className="card narrow">
      <h2>Add a New Trial</h2>
      <form onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="trialTitle">Trial Title <span className="req">*</span></label>
          <input id="trialTitle" value={trialTitle} onChange={(e) => setTrialTitle(e.target.value)}
                 placeholder="e.g. Phase II Study of Drug X in Type 2 Diabetes" />
        </div>
        <div className="field">
          <label htmlFor="sponsor">Sponsor / Institution <span className="req">*</span></label>
          <input id="sponsor" value={sponsor} onChange={(e) => setSponsor(e.target.value)}
                 placeholder="e.g. Stanford Medical Center" />
        </div>
        {error && <p className="err">{error}</p>}
        <button type="submit" className="submit-btn" disabled={busy}>
          {busy ? 'Saving...' : 'Submit Trial Listing'}
        </button>
      </form>
    </section>
  )
}