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

const FIELD_LABELS = {
  guest_email: 'Email',
  shipping_name: 'Full name',
  shipping_line1: 'Address line 1',
  shipping_city: 'City',
  shipping_state: 'State',
  shipping_postal_code: 'ZIP code',
  shipping_country: 'Country',
  shipping_phone: 'Phone',
  email: 'Email',
  password: 'Password',
  discount_code: 'Discount code',
}

function friendlyFieldMessage(field, msg = '') {
  if (field === 'guest_email' || field === 'email') return 'Enter a valid email address.'
  // Messages we write ourselves are already full sentences — show as-is.
  if (field === 'discount_code') return msg
  const label = FIELD_LABELS[field] || field.replace(/_/g, ' ')
  return `${label}: ${msg.replace(/\.$/, '')}.`
}

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`
  }

  const res = await fetch(`${BASE_URL}${path}`, { headers, ...options })
  if (!res.ok) {
    const body = await res.text()
    // Try to surface FastAPI's {"detail": "..."} message specifically
    // (e.g. a Stripe decline reason, a stock-conflict message) so
    // callers can show the real reason instead of a generic one.
    // Falls back to the raw body if it isn't JSON shaped that way.
    let detail
    try {
      detail = JSON.parse(body)?.detail
    } catch {
      // not JSON — leave detail undefined, err.message still has the raw body
    }
    const err = new Error(`API error ${res.status}: ${body}`)
    err.status = res.status
    // FastAPI validation errors (422) arrive as a LIST, one entry per
    // bad field: [{loc: ['body', 'guest_email'], msg: '...'}]. Turn
    // that into fieldErrors ({guest_email: 'Enter a valid email
    // address'}) plus a readable summary, instead of dropping it and
    // leaving callers to show a generic (and misleading) message.
    if (Array.isArray(detail)) {
      err.fieldErrors = {}
      for (const entry of detail) {
        const field = Array.isArray(entry?.loc) ? entry.loc[entry.loc.length - 1] : null
        if (typeof field === 'string' && !err.fieldErrors[field]) {
          err.fieldErrors[field] = friendlyFieldMessage(field, entry.msg)
        }
      }
      const messages = Object.values(err.fieldErrors)
      err.detail = messages.length ? messages.join(' ') : undefined
    } else {
      err.detail = typeof detail === 'string' ? detail : undefined
    }
    throw err
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  get: (path) => request(path),
  post: (path, data) => request(path, { method: 'POST', body: JSON.stringify(data) }),
  put: (path, data) => request(path, { method: 'PUT', body: JSON.stringify(data) }),
  patch: (path, data) => request(path, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (path) => request(path, { method: 'DELETE' }),
}
