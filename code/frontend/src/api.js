async function request(path, options = {}) {
  const res = await fetch(path, {
    credentials: 'include', // send the HTTP-only session cookie
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = data?.detail
    const err = new Error(typeof detail === 'string' ? detail : `Request failed (${res.status})`)
    err.status = res.status
    throw err
  }
  return data
}

export const api = {
  me: () => request('/api/auth/me'),
  register: (name, email, password) =>
  request('/api/auth/register', { method: 'POST', body: JSON.stringify({ name, email, password }) }),
  login: (email, password) =>
    request('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  listTrials: () => request('/api/trials'),
  createTrial: (trial) =>
    request('/api/trials', { method: 'POST', body: JSON.stringify(trial) }),
  updateTrial: (id, trial) =>
    request(`/api/trials/${id}`, { method: 'PUT', body: JSON.stringify(trial) }),
  deleteTrial: (id) => request(`/api/trials/${id}`, { method: 'DELETE' }),
}