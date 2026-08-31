import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { api, BASE_URL, getAuthToken } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function Transactions() {
  const { user } = useAuth()
  const isStaff = user && user.tier >= 2
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null) // full detail w/ lines
  const [refunding, setRefunding] = useState(false)

  function load() {
    setLoading(true)
    const endpoint = isStaff ? '/transactions/' : `/transactions/account/${user.id}`
    api
      .get(endpoint)
      .then((data) => setTransactions(data))
      .catch(() => setError('Could not load transactions.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [isStaff, user])

  async function openDetail(id) {
    setError(null)
    try {
      const detail = await api.get(`/transactions/${id}`)
      setSelected(detail)
    } catch {
      setError('Could not load transaction detail.')
    }
  }

  async function handleRefund(id) {
    if (!confirm('Refund this transaction in full?')) return
    setRefunding(true)
    setError(null)
    try {
      await api.post(`/transactions/${id}/refund`, {})
      setSelected(null)
      load()
    } catch (err) {
      // The backend returns 409 if this was already refunded — surface
      // that distinctly rather than a generic failure message.
      const msg = String(err.message || '')
      setError(
        msg.includes('409') ? 'This transaction has already been refunded.' : 'Refund failed.'
      )
    } finally {
      setRefunding(false)
    }
  }

  async function handleExport() {
    const res = await fetch(`${BASE_URL}/transactions/export`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    })
    if (!res.ok) {
      setError('Export failed.')
      return
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'transactions.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Layout>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Transactions</h1>
        {isStaff && (
          <button
            onClick={handleExport}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            Export CSV
          </button>
        )}
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      {loading && <p className="mt-4 text-gray-500">Loading…</p>}

      {!loading && (
        <div className="mt-6 overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {transactions.map((tx) => (
                <tr
                  key={tx.id}
                  onClick={() => openDetail(tx.id)}
                  className="cursor-pointer hover:bg-gray-50"
                >
                  <td className="px-4 py-3 font-medium text-gray-900">{tx.id}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(tx.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        tx.type === 'refunded'
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-green-100 text-green-700'
                      }`}
                    >
                      {tx.type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {tx.total != null ? `$${tx.total.toFixed(2)}` : '—'}
                  </td>
                </tr>
              ))}
              {transactions.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-gray-400">
                    No transactions yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/30 px-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg">
            <h2 className="text-lg font-semibold text-gray-900">Transaction #{selected.id}</h2>
            <p className="text-sm text-gray-500">
              {new Date(selected.created_at).toLocaleString()} · {selected.type}
            </p>

            <ul className="mt-4 divide-y divide-gray-100 text-sm">
              {selected.lines.map((l) => (
                <li key={l.id} className="flex justify-between py-2">
                  <span>
                    {l.quantity}× item #{l.item_id}
                  </span>
                  <span>${l.line_total.toFixed(2)}</span>
                </li>
              ))}
              {selected.lines.length === 0 && (
                <li className="py-2 text-gray-400">No line items (refund record).</li>
              )}
            </ul>

            <div className="mt-3 space-y-1 border-t border-gray-100 pt-3 text-sm">
              <div className="flex justify-between text-gray-500">
                <span>Subtotal</span>
                <span>${(selected.subtotal ?? 0).toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-gray-500">
                <span>Tax</span>
                <span>${(selected.tax_amount ?? 0).toFixed(2)}</span>
              </div>
              <div className="flex justify-between font-semibold text-gray-900">
                <span>Total</span>
                <span>${(selected.total ?? 0).toFixed(2)}</span>
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setSelected(null)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                Close
              </button>
              {isStaff && selected.type !== 'refunded' && selected.type !== 'voided' && (
                <button
                  onClick={() => handleRefund(selected.id)}
                  disabled={refunding}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
                >
                  {refunding ? 'Refunding…' : 'Refund'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
