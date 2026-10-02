import { useDispatch, useSelector } from 'react-redux'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { updateTrial } from '../store/trialsSlice'
import TrialForm from './TrialForm.jsx'

export default function UpdateRecord() {
  const trials = useSelector((s) => s.trials.items)
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const id = Number(params.get('id')) || ''
  const record = trials.find((t) => t.id === id)

  async function handleUpdate(trial) {
    await dispatch(updateTrial({ id, trial })).unwrap()
    navigate('/')
  }

  return (
    <section className="card narrow">
      <h2>Update a Trial</h2>
      <div className="field">
        <label htmlFor="pick">Select trial by ID</label>
        <select id="pick" value={id} onChange={(e) => setParams({ id: e.target.value })}>
          <option value="">-- choose an ID --</option>
          {trials.map((t) => <option key={t.id} value={t.id}>#{t.id} - {t.trial_title}</option>)}
        </select>
      </div>
      {record && (
        <TrialForm key={record.id} submitLabel={`Update Trial #${record.id}`} onSubmit={handleUpdate}
          initial={{
            trial_title: record.trial_title, nct_id: record.nct_id,
            enrollment_slots: record.enrollment_slots, status: record.status,
            sponsor_id: record.sponsor_id,
          }} />
      )}
    </section>
  )
}
