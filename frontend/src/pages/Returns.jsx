import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { api } from '../lib/api'

const STATUS_STYLE = {
  pending_inspection: 'bg-amber-50 text-amber-700',
  restocked: 'bg-green-50 text-green-700',
  restocked_discounted: 'bg-blue-50 text-blue-700',
  discarded: 'bg-gray-100 text-gray-500',
}

function LogReturnForm({ items, onLogged }) {
  const [refundTransactionId, setRefundTransactionId] = useState('')
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState([{ item_id: '', quantity: 1 }])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  function updateLine(i, patch) {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))
  }

  function addLine() {
    setLines((prev) => [...prev, { item_id: '', quantity: 1 }])
  }

  function removeLine(i) {
    setLines((prev) => prev.filter((_, idx) => idx !== i))
  }

  async function submit(e) {
    e.preventDefault()
    setError(null)
    const validLines = lines
      .filter((l) => l.item_id)
      .map((l) => ({ item_id: Number(l.item_id), quantity: Math.max(1, Number(l.quantity) || 1) }))
    if (!refundTransactionId || validLines.length === 0) {
      setError('Enter the refund transaction id and at least one item.')
      return
    }
    setSubmitting(true)
    try {
      await api.post('/returns/', {
        refund_transaction_id: Number(refundTransactionId),
        notes: notes || null,
        lines: validLines,
      })
      setRefundTransactionId('')
      setNotes('')
      setLines([{ item_id: '', quantity: 1 }])
      onLogged()
    } catch (err) {
      setError(err?.detail || 'Could not log this return — check the refund id and items.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h2 className="font-semibold text-gray-900">Log a return</h2>
      <p className="mt-1 text-sm text-gray-500">
        For a refund that's already been issued — the transaction id it returned to you.
      </p>

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      <label className="mt-4 block text-sm">
        <span className="mb-1 block text-gray-600">Refund transaction id</span>
        <input
          type="number"
          value={refundTransactionId}
          onChange={(e) => setRefundTransactionId(e.target.value)}
          className="w-full max-w-xs rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
        />
      </label>

      <div className="mt-4 space-y-2">
        <span className="block text-sm text-gray-600">Items coming back</span>
        {lines.map((line, i) => (
          <div key={i} className="flex items-center gap-2">
            <select
              value={line.item_id}
              onChange={(e) => updateLine(i, { item_id: e.target.value })}
              className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
            >
              <option value="">Select item…</option>
              {items.map((it) => (
                <option key={it.id} value={it.id}>
                  {it.name}
                </option>
              ))}
            </select>
            <input
              type="number"
              min="1"
              value={line.quantity}
              onChange={(e) => updateLine(i, { quantity: e.target.value })}
              className="w-20 rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
            />
            {lines.length > 1 && (
              <button
                type="button"
                onClick={() => removeLine(i)}
                className="text-gray-400 hover:text-red-600"
              >
                ✕
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={addLine}
          className="text-sm font-medium text-brand-600 hover:underline"
        >
          + Add another item
        </button>
      </div>

      <label className="mt-4 block text-sm">
        <span className="mb-1 block text-gray-600">Notes (optional)</span>
        <input
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
        />
      </label>

      <button
        type="submit"
        disabled={submitting}
        className="mt-4 rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:opacity-50"
      >
        {submitting ? 'Logging…' : 'Log return'}
      </button>
    </form>
  )
}

function ResolveLine({ line, itemsById, onResolved }) {
  const [showDiscount, setShowDiscount] = useState(false)
  const [discountPrice, setDiscountPrice] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const item = itemsById[line.item_id]

  async function resolve(status, extra = {}) {
    setBusy(true)
    setError(null)
    try {
      await api.patch(`/returns/${line.return_request_id}/lines/${line.id}`, {
        status,
        ...extra,
      })
      onResolved()
    } catch (err) {
      setError(err?.detail || 'Could not resolve this line — try again.')
      setBusy(false)
    }
  }

  return (
    <li className="rounded-lg border border-gray-100 p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-900">
          {line.quantity}× {item?.name || `Item #${line.item_id}`}
        </span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[line.status]}`}>
          {line.status.replace('_', ' ')}
        </span>
      </div>

      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          onClick={() => resolve('restocked')}
          disabled={busy}
          className="rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-600 disabled:opacity-50"
        >
          Restock as-is
        </button>

        {showDiscount ? (
          <>
            <input
              type="number"
              min="0"
              step="0.01"
              placeholder="Discount price"
              value={discountPrice}
              onChange={(e) => setDiscountPrice(e.target.value)}
              className="w-28 rounded-lg border border-gray-300 px-2 py-1 text-xs focus:border-brand-500 focus:outline-none"
            />
            <button
              onClick={() =>
                resolve('restocked_discounted', { discount_price: Number(discountPrice) })
              }
              disabled={busy || !discountPrice}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Confirm
            </button>
          </>
        ) : (
          <button
            onClick={() => setShowDiscount(true)}
            disabled={busy}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Restock at discount
          </button>
        )}

        <button
          onClick={() => resolve('discarded')}
          disabled={busy}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-50 disabled:opacity-50"
        >
          Discard
        </button>
      </div>
    </li>
  )
}

export default function Returns() {
  const [items, setItems] = useState([])
  const [pending, setPending] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  function loadPending() {
    setLoading(true)
    api
      .get('/returns/?pending_only=true')
      .then(setPending)
      .catch(() => setError('Could not load pending returns.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    api.get('/items/').then(setItems).catch(() => setItems([]))
    loadPending()
  }, [])

  const itemsById = Object.fromEntries(items.map((it) => [it.id, it]))
  const pendingLines = pending.flatMap((r) =>
    r.lines
      .filter((l) => l.status === 'pending_inspection')
      .map((l) => ({ ...l, return_request_id: r.id }))
  )

  return (
    <Layout>
      <h1 className="text-2xl font-semibold text-gray-900">Returns</h1>
      <p className="mt-1 text-gray-500">Log physical returns and decide what happens to them.</p>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <LogReturnForm items={items} onLogged={loadPending} />

        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-gray-900">Awaiting a decision</h2>

          {loading && <p className="mt-3 text-sm text-gray-500">Loading…</p>}

          {!loading && (
            <ul className="mt-3 space-y-2">
              {pendingLines.map((line) => (
                <ResolveLine
                  key={line.id}
                  line={line}
                  itemsById={itemsById}
                  onResolved={loadPending}
                />
              ))}
              {pendingLines.length === 0 && (
                <p className="text-sm text-gray-400">Nothing waiting on a decision right now.</p>
              )}
            </ul>
          )}
        </div>
      </div>
    </Layout>
  )
}
