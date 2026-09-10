import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { api } from '../lib/api'

const STATUS_FLOW = ['pending', 'processing', 'shipped', 'delivered']

const STATUS_STYLE = {
  pending: 'bg-amber-50 text-amber-700',
  processing: 'bg-blue-50 text-blue-700',
  shipped: 'bg-violet-50 text-violet-700',
  delivered: 'bg-green-50 text-green-700',
  cancelled: 'bg-gray-100 text-gray-500',
}

function nextStatus(current) {
  const i = STATUS_FLOW.indexOf(current)
  return i >= 0 && i < STATUS_FLOW.length - 1 ? STATUS_FLOW[i + 1] : null
}

function OrderCard({ order, onAdvance, onCancel, busy }) {
  const next = nextStatus(order.fulfillment_status)
  const [trackingNumber, setTrackingNumber] = useState(order.tracking_number || '')
  const shipTo = [order.shipping_name, order.shipping_line1, order.shipping_line2]
    .filter(Boolean)
    .join(', ')
  const shipLocation = [order.shipping_city, order.shipping_state, order.shipping_postal_code]
    .filter(Boolean)
    .join(', ')

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-medium text-gray-900">Order #{order.id}</p>
          <p className="mt-1 text-sm text-gray-500">
            {new Date(order.created_at).toLocaleString()}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLE[order.fulfillment_status]}`}
        >
          {order.fulfillment_status}
        </span>
      </div>

      {shipTo && (
        <p className="mt-3 text-sm text-gray-600">
          Ship to: {shipTo}
          {shipLocation && <>, {shipLocation}</>}
        </p>
      )}

      <p className="mt-1 text-sm text-gray-500">Total: ${order.total?.toFixed(2)}</p>

      {next === 'shipped' && (
        <input
          value={trackingNumber}
          onChange={(e) => setTrackingNumber(e.target.value)}
          placeholder="Tracking number (optional)"
          className="mt-2 w-full rounded-lg border border-gray-300 px-2 py-1 text-xs focus:border-brand-500 focus:outline-none"
        />
      )}

      <div className="mt-3 flex gap-2">
        {next && (
          <button
            onClick={() =>
              onAdvance(order.id, next, next === 'shipped' ? trackingNumber : undefined)
            }
            disabled={busy}
            className="rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-brand-600 disabled:opacity-50"
          >
            Mark {next}
          </button>
        )}
        <button
          onClick={() => onCancel(order.id)}
          disabled={busy}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs text-gray-600 transition hover:bg-gray-50 disabled:opacity-50"
        >
          Cancel order
        </button>
      </div>
    </div>
  )
}

export default function OrderQueue() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState(null)

  function load() {
    setLoading(true)
    api
      .get('/transactions/queue')
      .then(setOrders)
      .catch(() => setError('Could not load the order queue.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function updateStatus(id, status, trackingNumber) {
    setBusyId(id)
    setError(null)
    try {
      await api.patch(`/transactions/${id}/fulfillment`, {
        status,
        ...(trackingNumber ? { tracking_number: trackingNumber } : {}),
      })
      // Delivered/cancelled leave the queue entirely, so just refetch
      // rather than trying to patch the single row in place.
      load()
    } catch {
      setError('Could not update that order — try again.')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Layout>
      <h1 className="text-2xl font-semibold text-gray-900">Order queue</h1>
      <p className="mt-1 text-gray-500">Online orders awaiting fulfillment, oldest first.</p>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {loading && <p className="mt-6 text-gray-500">Loading…</p>}

      {!loading && (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {orders.map((order) => (
            <OrderCard
              key={order.id}
              order={order}
              busy={busyId === order.id}
              onAdvance={updateStatus}
              onCancel={(id) => updateStatus(id, 'cancelled')}
            />
          ))}
          {orders.length === 0 && (
            <p className="col-span-full text-gray-400">Nothing waiting on fulfillment right now.</p>
          )}
        </div>
      )}
    </Layout>
  )
}
