import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { api } from '../lib/api'
import { tierLabel, useClientConfig } from '../lib/clientConfig'

export default function Accounts() {
  const config = useClientConfig()
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reinstateId, setReinstateId] = useState('')

  function load() {
    setLoading(true)
    api
      .get('/accounts/')
      .then(setAccounts)
      .catch(() => setError('Could not load accounts.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function handleTierChange(id, tier) {
    try {
      await api.patch(`/accounts/${id}`, { tier: Number(tier) })
      load()
    } catch {
      setError('Could not update tier.')
    }
  }

  async function handleDeactivate(id) {
    if (!confirm('Deactivate this account?')) return
    try {
      await api.delete(`/accounts/${id}`)
      load()
    } catch {
      setError('Could not deactivate account.')
    }
  }

  async function handleReinstate(e) {
    e.preventDefault()
    if (!reinstateId) return
    try {
      await api.post(`/accounts/${reinstateId}/reinstate`)
      setReinstateId('')
      load()
    } catch {
      setError('Could not reinstate — check the account id.')
    }
  }

  const tierOptions = Object.keys(config.tier_labels).map(Number).sort((a, b) => a - b)

  return (
    <Layout>
      <h1 className="text-2xl font-semibold text-gray-900">Accounts</h1>
      <p className="mt-1 text-sm text-gray-500">
        Active accounts only. Deactivated accounts are archived, not deleted — reinstate one by
        id below if needed.
      </p>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      {loading && <p className="mt-4 text-gray-500">Loading…</p>}

      {!loading && (
        <div className="mt-6 overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Name / Email</th>
                <th className="px-4 py-3">Tier</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {accounts.map((a) => (
                <tr key={a.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900">{a.name || '—'}</p>
                    <p className="text-xs text-gray-500">{a.email}</p>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={a.tier}
                      onChange={(e) => handleTierChange(a.id, e.target.value)}
                      className="rounded-lg border border-gray-300 px-2 py-1 text-sm"
                    >
                      {tierOptions.map((t) => (
                        <option key={t} value={t}>
                          {tierLabel(t, config)}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDeactivate(a.id)}
                      className="text-red-600 hover:underline"
                    >
                      Deactivate
                    </button>
                  </td>
                </tr>
              ))}
              {accounts.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-gray-400">
                    No accounts.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <form onSubmit={handleReinstate} className="mt-6 flex items-end gap-2">
        <label className="text-sm">
          <span className="mb-1 block text-gray-600">Reinstate account by id</span>
          <input
            value={reinstateId}
            onChange={(e) => setReinstateId(e.target.value)}
            className="w-32 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
          />
        </label>
        <button
          type="submit"
          className="rounded-lg border border-gray-300 px-4 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
        >
          Reinstate
        </button>
      </form>
    </Layout>
  )
}
