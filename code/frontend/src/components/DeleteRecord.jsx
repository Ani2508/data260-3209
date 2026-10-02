import { useState } from 'react'
import { useDispatch } from 'react-redux'
import { deleteTrial } from '../store/trialsSlice'

// Delete button shown next to each record on the Home screen.
export default function DeleteButton({ id }) {
  const dispatch = useDispatch()
  const [busy, setBusy] = useState(false)

  async function handleDelete() {
    if (!window.confirm(`Delete trial #${id}?`)) return
    setBusy(true)
    // fulfilled -> reducer removes the record from state; rejected -> slice stores the error
    await dispatch(deleteTrial(id))
    setBusy(false)
  }

  return (
    <button type="button" className="btn-small danger" onClick={handleDelete} disabled={busy}>
      {busy ? 'Deleting...' : 'Delete'}
    </button>
  )
}
