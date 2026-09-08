import { useState } from 'react'
import { api } from '../lib/api'

export default function NewsletterSignup() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('idle') // idle | submitting | done | error

  async function handleSubmit(e) {
    e.preventDefault()
    if (!email) return
    setStatus('submitting')
    try {
      await api.post('/newsletter/', { email })
      setStatus('done')
      setEmail('')
    } catch {
      setStatus('error')
    }
  }

  if (status === 'done') {
    return (
      <p className="text-sm font-medium text-brand-600">You're on the list — thanks!</p>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-sm">
      <p className="text-sm font-medium text-gray-700">Get discounts by email</p>
      <div className="mt-2 flex gap-2">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        <button
          type="submit"
          disabled={status === 'submitting'}
          className="shrink-0 rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:opacity-60"
        >
          {status === 'submitting' ? 'Joining…' : 'Sign up'}
        </button>
      </div>
      {status === 'error' && (
        <p className="mt-1 text-xs text-red-600">Something went wrong — try again.</p>
      )}
    </form>
  )
}
