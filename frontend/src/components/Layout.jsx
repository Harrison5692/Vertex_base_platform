import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { useClientConfig } from '../lib/clientConfig'
import AuthModal from './AuthModal'

const navLinkClass = ({ isActive }) =>
  `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
    isActive ? 'bg-brand-50 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
  }`

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const config = useClientConfig()
  const [showAuth, setShowAuth] = useState(false)
  const isStaff = user && user.tier >= 2

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
        <div className="flex items-center gap-6">
          <span className="font-semibold text-gray-900">{config.app_name}</span>
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={navLinkClass}>
              Home
            </NavLink>
            <NavLink to="/items" className={navLinkClass}>
              Items
            </NavLink>
            <NavLink to="/checkout" className={navLinkClass}>
              Checkout
            </NavLink>
            {user && (
              <NavLink to="/transactions" className={navLinkClass}>
                Transactions
              </NavLink>
            )}
            {user && (
              <NavLink to="/notifications" className={navLinkClass}>
                Notifications
              </NavLink>
            )}
            {isStaff && (
              <NavLink to="/accounts" className={navLinkClass}>
                Accounts
              </NavLink>
            )}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          {user ? (
            <>
              <span className="text-sm text-gray-500">{user.email}</span>
              <button
                onClick={logout}
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 transition hover:bg-gray-50"
              >
                Log out
              </button>
            </>
          ) : (
            <button
              onClick={() => setShowAuth(true)}
              className="rounded-lg bg-brand-500 px-4 py-1.5 text-sm font-semibold text-white transition hover:bg-brand-600"
            >
              Log in
            </button>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>

      {showAuth && <AuthModal onClose={() => setShowAuth(false)} />}
    </div>
  )
}
