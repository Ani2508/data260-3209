// HW7: JWT bearer auth. The access token is kept in sessionStorage and sent
// as "Authorization: Bearer <token>" (the HW4 session cookie is no longer used).
const TOKEN_KEY = 's3209_access_token'

export const tokenStore = {
  get: () => { try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null } },
  set: (t) => { try { sessionStorage.setItem(TOKEN_KEY, t) } catch { /* storage blocked */ } },
  clear: () => { try { sessionStorage.removeItem(TOKEN_KEY) } catch { /* storage blocked */ } },
}

async function request(path, options = {}) {
  const token = tokenStore.get()
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
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
  register: (username, password) =>
    request('/api/auth/register', { method: 'POST', body: JSON.stringify({ username, password }) }),
  login: async (username, password) => {
    const out = await request('/api/auth/login', {
      method: 'POST', body: JSON.stringify({ username, password }),
    })
    tokenStore.set(out.access_token)
    return request('/api/auth/me')
  },
  logout: async () => { tokenStore.clear() },
  listTrials: () => request('/api/trials'),
  createTrial: (trial) =>
    request('/api/trials', { method: 'POST', body: JSON.stringify(trial) }),
  updateTrial: (id, trial) =>
    request(`/api/trials/${id}`, { method: 'PUT', body: JSON.stringify(trial) }),
  deleteTrial: (id) => request(`/api/trials/${id}`, { method: 'DELETE' }),
}
