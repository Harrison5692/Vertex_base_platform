import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import CategorySidebar from '../components/CategorySidebar'
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
  // allItems (unfiltered) drives the category list; items is the
  // filtered set actually shown, re-fetched from the server whenever
  // the category changes so it reuses the existing /items?category=
  // filter instead of re-implementing filtering client-side.
  const [allItems, setAllItems] = useState([])
  const [items, setItems] = useState([])
  const [category, setCategory] = useState(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [unreadCount, setUnreadCount] = useState(null)
  const isStaff = user && user.tier >= 2

  useEffect(() => {
    api.get('/items/').then(setAllItems).catch(() => setAllItems([]))
    if (user) {
      api
        .get('/notifications/')
        .then((notifs) => setUnreadCount(notifs.filter((n) => !n.read_at).length))
        .catch(() => setUnreadCount(0))
    }
  }, [user])

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (category) params.set('category', category)
    if (search) params.set('q', search)
    const qs = params.toString()
    api
      .get(`/items/${qs ? `?${qs}` : ''}`)
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [category, search])

  const categories = useMemo(
    () => [...new Set(allItems.map((i) => i.category).filter(Boolean))].sort(),
    [allItems]
  )

  return (
    <Layout banner={<StorefrontBanner />}>
      {isStaff && (
        <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Items" value={allItems.length} to="/items" />
          <StatCard label="New sale" value="Checkout →" to="/checkout" />
          <StatCard label="Unread notifications" value={unreadCount ?? '—'} to="/notifications" />
          <StatCard label="Accounts" value="Manage →" to="/accounts" />
          <StatCard label="Order queue" value="Fulfill →" to="/orders/queue" />
        </div>
      )}

      <div className="flex flex-col gap-8 sm:flex-row">
        <CategorySidebar categories={categories} active={category} onSelect={setCategory} />

        <div className="flex-1">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search products…"
            className="mb-4 w-full max-w-sm rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />

          {loading && <p className="text-gray-500">Loading…</p>}

          {!loading && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              {items.map((item) => (
                <ProductCard key={item.id} item={item} />
              ))}
              {items.length === 0 && (
                <p className="col-span-full text-gray-400">
                  {search ? `No products match "${search}".` : 'No items in this category yet.'}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
