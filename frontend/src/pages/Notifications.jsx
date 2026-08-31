import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { api } from '../lib/api'

export default function Notifications() {
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  function load() {
    setLoading(true)
    api
      .get('/notifications/')
      .then(setNotifications)
      .catch(() => setError('Could not load notifications.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function markRead(id) {
    // Optimistic — flip it locally right away, roll back only if the
    // request actually fails.
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n))
    )
    try {
      await api.post(`/notifications/${id}/read`)
    } catch {
      load() // re-sync with the server on failure
    }
  }

  return (
    <Layout>
      <h1 className="text-2xl font-semibold text-gray-900">Notifications</h1>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      {loading && <p className="mt-4 text-gray-500">Loading…</p>}

      {!loading && (
        <ul className="mt-6 space-y-2">
          {notifications.map((n) => (
            <li
              key={n.id}
              className={`flex items-start justify-between rounded-xl border p-4 text-sm ${
                n.read_at ? 'border-gray-200 bg-white text-gray-500' : 'border-brand-200 bg-brand-50'
              }`}
            >
              <div>
                <p className={n.read_at ? '' : 'font-medium text-gray-900'}>{n.message}</p>
                <p className="mt-1 text-xs text-gray-400">
                  {new Date(n.created_at).toLocaleString()}
                </p>
              </div>
              {!n.read_at && (
                <button
                  onClick={() => markRead(n.id)}
                  className="ml-4 shrink-0 text-xs font-medium text-brand-600 hover:underline"
                >
                  Mark read
                </button>
              )}
            </li>
          ))}
          {notifications.length === 0 && (
            <li className="rounded-xl border border-gray-200 bg-white p-8 text-center text-gray-400">
              No notifications.
            </li>
          )}
        </ul>
      )}
    </Layout>
  )
}
