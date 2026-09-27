import { Link } from 'react-router-dom'

export default function Home({ user, trials, loading, error }) {
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

      {loading && <p className="state state-loading">Loading trial records...</p>}
      {error && <p className="state state-error">{error}</p>}
      {!loading && !error && trials.length === 0 &&
        <p className="side-empty">No trials yet. Click "Add Trial" to create one.</p>}

      {trials.length > 0 && (
        <div className="table-wrap">
          <table className="trial-table">
            <thead>
              <tr><th>ID</th><th>Trial Title</th><th>Sponsor</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {trials.map((t) => (
                <tr key={t.id}>
                  <td>{t.id}</td>
                  <td>{t.trialTitle}</td>
                  <td>{t.sponsor}</td>
                  <td className="row-actions">
                    <Link to={`/update?id=${t.id}`}>Edit</Link>
                    <Link to={`/delete?id=${t.id}`} className="danger">Delete</Link>
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