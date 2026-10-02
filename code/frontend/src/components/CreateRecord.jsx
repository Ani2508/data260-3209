import { useDispatch } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { createTrial } from '../store/trialsSlice'
import TrialForm from './TrialForm.jsx'

const EMPTY_TRIAL = { trial_title: '', nct_id: '', enrollment_slots: 0, status: 'Recruiting', sponsor_id: '' }

export default function CreateRecord() {
  const dispatch = useDispatch()
  const navigate = useNavigate()

  // dispatch the createTrial thunk; unwrap() throws the error message on failure
  async function handleCreate(trial) {
    await dispatch(createTrial(trial)).unwrap()
    navigate('/') // Home re-renders from Redux state with the new record
  }

  return (
    <section className="card narrow">
      <h2>Add a New Trial</h2>
      <TrialForm initial={EMPTY_TRIAL} submitLabel="Submit Trial Listing" onSubmit={handleCreate} />
    </section>
  )
}
