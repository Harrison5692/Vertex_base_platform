import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

const emptyForm = {
  name: '',
  description: '',
  category: '',
  price: '',
  sku: '',
  stock_quantity: '',
  low_stock_threshold: '',
  duration_minutes: '',
}

function toPayload(form) {
  // Empty string -> null for every optional numeric/text field, so we
  // don't send "" where the API expects a number or nothing at all.
  const num = (v) => (v === '' ? null : Number(v))
  return {
    name: form.name,
    description: form.description || null,
    category: form.category || null,
    price: num(form.price),
    sku: form.sku || null,
    stock_quantity: num(form.stock_quantity),
    low_stock_threshold: num(form.low_stock_threshold),
    duration_minutes: num(form.duration_minutes),
  }
}

export default function Items() {
  const { user } = useAuth()
  const isStaff = user && user.tier >= 2
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  function load() {
    setLoading(true)
    api
      .get('/items/')
      .then(setItems)
      .catch(() => setError('Could not load items.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  function startCreate() {
    setForm(emptyForm)
    setEditingId(null)
    setShowForm(true)
  }

  function startEdit(item) {
    setForm({
      name: item.name ?? '',
      description: item.description ?? '',
      category: item.category ?? '',
      price: item.price ?? '',
      sku: item.sku ?? '',
      stock_quantity: item.stock_quantity ?? '',
      low_stock_threshold: item.low_stock_threshold ?? '',
      duration_minutes: item.duration_minutes ?? '',
    })
    setEditingId(item.id)
    setShowForm(true)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = toPayload(form)
      if (editingId) {
        await api.patch(`/items/${editingId}`, payload)
      } else {
        await api.post('/items/', payload)
      }
      setShowForm(false)
      load()
    } catch {
      setError('Could not save item — check the values and try again.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this item?')) return
    try {
      await api.delete(`/items/${id}`)
      load()
    } catch {
      setError('Could not delete item.')
    }
  }

  return (
    <Layout>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Items</h1>
        {isStaff && (
          <button
            onClick={startCreate}
            className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-600"
          >
            + New item
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
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3">Price</th>
                <th className="px-4 py-3">Stock</th>
                {isStaff && <th className="px-4 py-3"></th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((item) => {
                const low =
                  item.low_stock_threshold != null &&
                  item.stock_quantity != null &&
                  item.stock_quantity <= item.low_stock_threshold
                return (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{item.name}</td>
                    <td className="px-4 py-3 text-gray-500">{item.category || '—'}</td>
                    <td className="px-4 py-3 text-gray-500">
                      {item.price != null ? `$${item.price.toFixed(2)}` : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {item.stock_quantity != null ? (
                        <span className={low ? 'font-medium text-amber-600' : 'text-gray-500'}>
                          {item.stock_quantity}
                          {low ? ' (low)' : ''}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    {isStaff && (
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => startEdit(item)}
                          className="text-brand-600 hover:underline"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(item.id)}
                          className="ml-3 text-red-600 hover:underline"
                        >
                          Delete
                        </button>
                      </td>
                    )}
                  </tr>
                )
              })}
              {items.length === 0 && (
                <tr>
                  <td colSpan={isStaff ? 5 : 4} className="px-4 py-8 text-center text-gray-400">
                    No items yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/30 px-4">
          <form
            onSubmit={handleSubmit}
            className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg"
          >
            <h2 className="mb-4 text-lg font-semibold text-gray-900">
              {editingId ? 'Edit item' : 'New item'}
            </h2>

            <div className="grid grid-cols-2 gap-3">
              <label className="col-span-2 text-sm">
                <span className="mb-1 block text-gray-600">Name</span>
                <input
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                />
              </label>
              <label className="col-span-2 text-sm">
                <span className="mb-1 block text-gray-600">Description</span>
                <input
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-gray-600">Category</span>
                <input
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-gray-600">Price</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.price}
                  onChange={(e) => setForm({ ...form, price: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-gray-600">SKU</span>
                <input
                  value={form.sku}
                  onChange={(e) => setForm({ ...form, sku: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-gray-600">Duration (min)</span>
                <input
                  type="number"
                  min="0"
                  value={form.duration_minutes}
                  onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-gray-600">Stock qty</span>
                <input
                  type="number"
                  min="0"
                  value={form.stock_quantity}
                  onChange={(e) => setForm({ ...form, stock_quantity: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-gray-600">Low-stock alert at</span>
                <input
                  type="number"
                  min="0"
                  value={form.low_stock_threshold}
                  onChange={(e) => setForm({ ...form, low_stock_threshold: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
                />
              </label>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-60"
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </form>
        </div>
      )}
    </Layout>
  )
}
