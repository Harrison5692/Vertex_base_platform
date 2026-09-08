import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import StorefrontBanner from '../components/StorefrontBanner'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

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

function ProductCard({ item }) {
  return (
    <Link
      to={`/items/${item.id}`}
      className="overflow-hidden rounded-xl border border-gray-200 bg-white text-left shadow-sm transition hover:border-brand-300 hover:shadow"
    >
      {item.image_url ? (
        <img src={item.image_url} alt={item.name} className="h-32 w-full object-cover" />
      ) : (
        <div className="h-32 w-full bg-gray-100" />
      )}
      <div className="p-3">
        <p className="truncate font-medium text-gray-900">{item.name}</p>
        <p className="mt-1 text-sm text-gray-500">
          {item.price != null ? `$${item.price.toFixed(2)}` : 'Price on request'}
        </p>
      </div>
    </Link>
  )
}

export default function Home() {
  const { user } = useAuth()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [unreadCount, setUnreadCount] = useState(null)
  const isStaff = user && user.tier >= 2

  useEffect(() => {
    api
      .get('/items/')
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
    if (user) {
      api
        .get('/notifications/')
        .then((notifs) => setUnreadCount(notifs.filter((n) => !n.read_at).length))
        .catch(() => setUnreadCount(0))
    }
  }, [user])

  return (
    <Layout>
      <StorefrontBanner />

      {user && (
        <p className="-mt-6 mb-6 text-sm text-gray-500">Welcome back, {user.name || user.email}</p>
      )}

      {isStaff && (
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Items" value={items.length} to="/items" />
          <StatCard label="New sale" value="Checkout →" to="/checkout" />
          <StatCard label="Unread notifications" value={unreadCount ?? '—'} to="/notifications" />
          <StatCard label="Accounts" value="Manage →" to="/accounts" />
        </div>
      )}

      <h2 className="mt-8 text-lg font-semibold text-gray-900">Shop</h2>

      {loading && <p className="mt-4 text-gray-500">Loading…</p>}

      {!loading && (
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
          {items.map((item) => (
            <ProductCard key={item.id} item={item} />
          ))}
          {items.length === 0 && (
            <p className="col-span-full text-gray-400">No items available yet.</p>
          )}
        </div>
      )}
    </Layout>
  )
}
