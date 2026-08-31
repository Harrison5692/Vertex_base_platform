import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useClientConfig } from '../lib/clientConfig'

function StatCard({ label, value, to }) {
  return (
    <Link
      to={to}
      className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition hover:border-brand-300 hover:shadow"
    >
      <p className="text-sm text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
    </Link>
  )
}

export default function Home() {
  const { user } = useAuth()
  const config = useClientConfig()
  const [itemCount, setItemCount] = useState(null)
  const [unreadCount, setUnreadCount] = useState(null)
  const isStaff = user && user.tier >= 2

  useEffect(() => {
    api.get('/items/').then((items) => setItemCount(items.length)).catch(() => setItemCount(0))
    if (user) {
      api
        .get('/notifications/')
        .then((notifs) => setUnreadCount(notifs.filter((n) => !n.read_at).length))
        .catch(() => setUnreadCount(0))
    }
  }, [user])

  return (
    <Layout>
      <h1 className="text-2xl font-semibold text-gray-900">
        Welcome{user?.name ? `, ${user.name}` : ''}
      </h1>
      <p className="mt-1 text-gray-500">{config.app_name}</p>

      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatCard label="Items" value={itemCount ?? '—'} to="/items" />
        <StatCard label="New sale" value="Checkout →" to="/checkout" />
        {user && (
          <StatCard label="Unread notifications" value={unreadCount ?? '—'} to="/notifications" />
        )}
        {isStaff && <StatCard label="Transaction history" value="View all →" to="/transactions" />}
        {isStaff && <StatCard label="Accounts" value="Manage →" to="/accounts" />}
      </div>
    </Layout>
  )
}
