/**
 * Thin fetch wrapper — swap the base URL per environment via Vite env vars.
 * Keeps every component from having to know API details directly.
 */
const BASE_URL = import.meta.env.VITE_API_URL || '/api'

let authToken = null

/** Called by the auth context whenever the token changes (login/logout). */
export function setAuthToken(token) {
  authToken = token
}

/** Exposed for the rare case a component needs a raw fetch() itself
 * (e.g. downloading a non-JSON file like a CSV export) rather than
 * going through the request() helper below. */
export function getAuthToken() {
  return authToken
}

export { BASE_URL }

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`
  }

  const res = await fetch(`${BASE_URL}${path}`, { headers, ...options })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API error ${res.status}: ${body}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  get: (path) => request(path),
  post: (path, data) => request(path, { method: 'POST', body: JSON.stringify(data) }),
  patch: (path, data) => request(path, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (path) => request(path, { method: 'DELETE' }),
}
