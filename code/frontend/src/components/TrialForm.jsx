import { useState } from 'react'
import { useSelector } from 'react-redux'

const STATUSES = ['Recruiting', 'Active - Not Recruiting', 'Completed', 'Terminated']

// Shared form used by the Create and Update screens.
export default function TrialForm({ initial, submitLabel, onSubmit }) {
  const sponsors = useSelector((s) => s.sponsors.items)
  const [form, setForm] = useState(initial)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!form.trial_title.trim() || !form.sponsor_id) { setError('Title and sponsor are required.'); return }
    if (!/^NCT\d{8}$/.test(form.nct_id.trim().toUpperCase())) {
      setError('NCT ID must be "NCT" followed by 8 digits, e.g. NCT01234567.'); return
    }
    setBusy(true)
    try {
      await onSubmit({
        ...form,
        trial_title: form.trial_title.trim(),
        nct_id: form.nct_id.trim().toUpperCase(),
        enrollment_slots: Number(form.enrollment_slots) || 0,
        sponsor_id: Number(form.sponsor_id),
      })
    } catch (msg) {
      setError(String(msg))
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="trial_title">Trial Title <span className="req">*</span></label>
        <input id="trial_title" value={form.trial_title} onChange={set('trial_title')}
               placeholder="e.g. Phase II Study of Drug X in Type 2 Diabetes" />
      </div>
      <div className="field">
        <label htmlFor="nct_id">NCT ID (unique) <span className="req">*</span></label>
        <input id="nct_id" value={form.nct_id} onChange={set('nct_id')} placeholder="NCT01234567" />
      </div>
      <div className="field">
        <label htmlFor="enrollment_slots">Open Enrollment Slots</label>
        <input id="enrollment_slots" type="number" min="0" value={form.enrollment_slots}
               onChange={set('enrollment_slots')} />
      </div>
      <div className="field">
        <label htmlFor="status">Status</label>
        <select id="status" value={form.status} onChange={set('status')}>
          {STATUSES.map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor="sponsor_id">Sponsor <span className="req">*</span></label>
        <select id="sponsor_id" value={form.sponsor_id} onChange={set('sponsor_id')}>
          <option value="">-- choose a sponsor --</option>
          {sponsors.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.country})</option>)}
        </select>
      </div>
      {error && <p className="err">{error}</p>}
      <button type="submit" className="submit-btn" disabled={busy}>
        {busy ? 'Saving...' : submitLabel}
      </button>
    </form>
  )
}
