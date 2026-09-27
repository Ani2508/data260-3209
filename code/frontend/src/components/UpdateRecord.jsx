import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

export default function UpdateRecord({ trials, onUpdate }) {
  const [params] = useSearchParams()
  const id = Number(params.get('id'))
  const record = trials.find((t) => t.id === id)

  const [trialTitle, setTrialTitle] = useState('')
  const [sponsor, setSponsor] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  // Fill the form with the current values
  useEffect(() => {
    if (record) { setTrialTitle(record.trialTitle); setSponsor(record.sponsor) }
  }, [record])

  if (!record) {
    return (
      <section className="card narrow">
        <p className="state state-error">Trial not found. Choose "Edit" from the list.</p>
        <Link to="/">Back to list</Link>
      </section>
    )
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const title = trialTitle.trim()
    const spon = sponsor.trim()
    if (!title || !spon) { setError('Both fields are required.'); return }
    setBusy(true)
    try {
      await onUpdate(id, { trialTitle: title, sponsor: spon })
      navigate('/')
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <section className="card narrow">
      <h2>Update Trial #{id}</h2>
      <form onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="trialTitle">Trial Title <span className="req">*</span></label>
          <input id="trialTitle" value={trialTitle} onChange={(e) => setTrialTitle(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="sponsor">Sponsor / Institution <span className="req">*</span></label>
          <input id="sponsor" value={sponsor} onChange={(e) => setSponsor(e.target.value)} />
        </div>
        {error && <p className="err">{error}</p>}
        <button type="submit" className="submit-btn" disabled={busy}>
          {busy ? 'Saving...' : 'Update Trial Listing'}
        </button>
      </form>
    </section>
  )
}