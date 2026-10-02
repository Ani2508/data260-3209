import axios from 'axios'

// One axios instance for the FastAPI backend (Vite proxies /api -> :8509).
export const http = axios.create({
  baseURL: '/api',
  withCredentials: true, // send the HTTP-only session cookie
  timeout: 10000,
})

// Turn any axios error into a short, readable message for the UI.
export function errorMessage(err) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => `${d.loc?.at(-1)}: ${d.msg}`).join('; ')
  if (err.code === 'ECONNABORTED') return 'Request timed out'
  return err.message || 'Request failed'
}
