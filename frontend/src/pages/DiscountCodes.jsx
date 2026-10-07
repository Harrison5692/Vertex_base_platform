import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { api } from '../lib/api'

const EMPTY_FORM = {
  code: '',
  kind: 'percent',
  value: '',
  min_subtotal: '',
  expires_at: '',
  max_uses: '',
}

function describe(dc) {
  const off = dc.kind === 'percent' ? `${dc.value}% off` : `$${dc.value.toFixed(2)} off`
  const rules = []
  if (dc.min_subtotal != null) rules.push(`min $${dc.min_subtotal.toFixed(2)}`)
  if (dc.expires_at) rules.push(`expires ${new Date(dc.expires_at + 'Z').toLocaleDateString()}`)
  if (dc.max_uses != null) rules.push(`${dc.uses_count}/${dc.max_uses} used`)
  else rules.push(`${dc.uses_count} used`)
  return `${off} · ${rules.join(' · ')}`
}

/** Manager-only (tier 3+). Codes are deactivated, never deleted —
 * past orders keep showing the code they used. */
export default function DiscountCodes() {
  const [codes, setCodes] = useState([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  async function load() {
    try {
      setCodes(await api.get('/discount-codes/'))
    } catch {
      setError('Could not load discount codes.')
    }
  }

  useEffect(() => {
    let cancelled = false
    api
      .get('/discount-codes/')
      .then((rows) => !cancelled && setCodes(rows))
      .catch(() => !cancelled && setError('Could not load discount codes.'))
    return () => {
      cancelled = true
    }
  }, [])

  async function create() {
    setError(null)
    if (!form.code.trim() || !form.value) {
      setError('Enter a code and an amount.')
      return
    }
    setSaving(true)
    try {
      await api.post('/discount-codes/', {
        code: form.code.trim(),
        kind: form.kind,
        value: Number(form.value),
        min_subtotal: form.min_subtotal === '' ? null : Number(form.min_subtotal),
        // End of the chosen day, so "expires Oct 31" works all of Oct 31.
        expires_at: form.expires_at ? `${form.expires_at}T23:59:59` : null,
        max_uses: form.max_uses === '' ? null : Number(form.max_uses),
      })
      setForm(EMPTY_FORM)
      await load()
    } catch (err) {
      setError(err?.detail || 'Could not create that code.')
    } finally {
      setSaving(false)
    }
  }

  async function toggle(dc) {
    setError(null)
    try {
      await api.patch(`/discount-codes/${dc.id}`, { is_active: !dc.is_active })
      await load()
    } catch (err) {
      setError(err?.detail || 'Could not update that code.')
    }
  }

  const field =
    'w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none'

  return (
    <Layout>
      <h1 className="text-2xl font-semibold text-gray-900">Discount codes</h1>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-gray-900">New code</h2>
          <div className="mt-3 space-y-2 text-sm">
            <input
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              placeholder="Code (e.g. FALL15)"
              className={`${field} uppercase`}
            />
            <div className="grid grid-cols-2 gap-2">
              <select
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value })}
                className={field}
              >
                <option value="percent">% off</option>
                <option value="fixed">$ off</option>
              </select>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.value}
                onChange={(e) => setForm({ ...form, value: e.target.value })}
                placeholder={form.kind === 'percent' ? 'Percent' : 'Dollars'}
                className={field}
              />
            </div>
            <p className="pt-1 text-xs text-gray-500">Optional limits</p>
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.min_subtotal}
              onChange={(e) => setForm({ ...form, min_subtotal: e.target.value })}
              placeholder="Minimum order ($)"
              className={field}
            />
            <label className="block">
              <span className="mb-1 block text-xs text-gray-500">Expires after</span>
              <input
                type="date"
                value={form.expires_at}
                onChange={(e) => setForm({ ...form, expires_at: e.target.value })}
                className={field}
              />
            </label>
            <input
              type="number"
              min="1"
              step="1"
              value={form.max_uses}
              onChange={(e) => setForm({ ...form, max_uses: e.target.value })}
              placeholder="Max total uses"
              className={field}
            />
            <button
              onClick={create}
              disabled={saving}
              className="mt-2 w-full rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Create code'}
            </button>
          </div>
        </div>

        <div className="lg:col-span-2">
          <ul className="divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white shadow-sm">
            {codes.map((dc) => (
              <li key={dc.id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p
                    className={`font-mono font-semibold ${dc.is_active ? 'text-gray-900' : 'text-gray-400 line-through'}`}
                  >
                    {dc.code}
                  </p>
                  <p className="truncate text-sm text-gray-500">{describe(dc)}</p>
                </div>
                <button
                  onClick={() => toggle(dc)}
                  className="shrink-0 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
                >
                  {dc.is_active ? 'Deactivate' : 'Reactivate'}
                </button>
              </li>
            ))}
            {codes.length === 0 && (
              <li className="px-4 py-6 text-center text-sm text-gray-400">No codes yet.</li>
            )}
          </ul>
        </div>
      </div>
    </Layout>
  )
}
