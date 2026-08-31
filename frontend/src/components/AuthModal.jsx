import { useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function AuthModal({ onClose }) {
  const { login } = useAuth()
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [emailOptIn, setEmailOptIn] = useState(false)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (mode === 'register') {
        // tier hardcoded to 1 (client) — public registration should
        // never let a caller choose their own tier; see the pre-launch
        // checklist in CUSTOMIZING.md for locking this down further.
        await api.post('/auth/register', {
          email,
          password,
          tier: 1,
          is_active: true,
          email_opt_in: emailOptIn,
        })
      }
      await login(email, password)
      onClose()
    } catch (err) {
      setError(
        mode === 'register'
          ? 'Could not create account — email may already be registered.'
          : 'Incorrect email or password.'
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-xl bg-white p-6 shadow-lg"
      >
        <div className="mb-4 flex gap-4 border-b border-gray-100">
          <button
            type="button"
            onClick={() => setMode('login')}
            className={`pb-2 text-sm font-medium ${
              mode === 'login' ? 'border-b-2 border-brand-500 text-brand-700' : 'text-gray-400'
            }`}
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => setMode('register')}
            className={`pb-2 text-sm font-medium ${
              mode === 'register' ? 'border-b-2 border-brand-500 text-brand-700' : 'text-gray-400'
            }`}
          >
            Create account
          </button>
        </div>

        <label className="mb-1 block text-sm font-medium text-gray-600">Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="mb-3 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />

        <label className="mb-1 block text-sm font-medium text-gray-600">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={mode === 'register' ? 8 : undefined}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />

        {mode === 'register' && (
          <label className="mt-3 flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={emailOptIn}
              onChange={(e) => setEmailOptIn(e.target.checked)}
            />
            Send me occasional updates by email
          </label>
        )}

        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-60"
          >
            {submitting ? 'Please wait…' : mode === 'register' ? 'Create account' : 'Sign in'}
          </button>
        </div>
      </form>
    </div>
  )
}
