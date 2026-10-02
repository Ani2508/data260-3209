import { useSelector } from 'react-redux'
import { Link } from 'react-router-dom'
import DeleteButton from './DeleteRecord.jsx'

export default function Home({ user }) {
  // Read everything from the Redux store
  const { items: trials, status, error, message } = useSelector((s) => s.trials)

  if (!user) {
    return (
      <section className="card narrow">
        <p className="state state-info">Login required</p>
        <p className="side-empty">Please <Link to="/login">log in</Link> to view and manage trial records.</p>
      </section>
    )
  }

  return (
    <section className="card">
      <div className="side-head">
        <h2>All Trial Records</h2>
        <span className="count-badge">{trials.length}</span>
      </div>

      {message && <p className="state state-info">{message}</p>}
      {status === 'loading' && <p className="state state-loading">Loading trial records...</p>}
      {error && <p className="state state-error">{error}</p>}
      {status === 'succeeded' && trials.length === 0 &&
        <p className="side-empty">No trials yet. Click "Add Trial" to create one.</p>}

      {trials.length > 0 && (
        <div className="table-wrap">
          <table className="trial-table">
            <thead>
              <tr><th>ID</th><th>Trial Title</th><th>NCT ID</th><th>Slots</th>
                <th>Status</th><th>Sponsor</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {trials.map((t) => (
                <tr key={t.id}>
                  <td>{t.id}</td>
                  <td>{t.trial_title}</td>
                  <td>{t.nct_id}</td>
                  <td>{t.enrollment_slots}</td>
                  <td>{t.status}</td>
                  <td>{t.sponsor_name}</td>
                  <td className="row-actions">
                    <Link to={`/update?id=${t.id}`}>Edit</Link>
                    <DeleteButton id={t.id} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
