import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import { api } from '../lib/api'
import { useCart } from '../lib/cart'

export default function ProductDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { addToCart } = useCart()
  const [item, setItem] = useState(null)
  const [error, setError] = useState(null)
  const [added, setAdded] = useState(false)

  useEffect(() => {
    setError(null)
    setItem(null)
    api
      .get(`/items/${id}`)
      .then(setItem)
      .catch(() => setError('Could not load this product.'))
  }, [id])

  function handleAddToCart() {
    addToCart(item)
    setAdded(true)
    setTimeout(() => setAdded(false), 1500)
  }

  if (error) {
    return (
      <Layout>
        <p className="text-sm text-red-600">{error}</p>
        <Link to="/" className="mt-3 inline-block text-sm text-brand-600 hover:underline">
          ← Back to shop
        </Link>
      </Layout>
    )
  }

  if (!item) {
    return (
      <Layout>
        <p className="text-gray-500">Loading…</p>
      </Layout>
    )
  }

  const outOfStock =
    item.stock_quantity != null && item.stock_quantity <= 0

  return (
    <Layout>
      <Link to="/" className="text-sm text-brand-600 hover:underline">
        ← Back to shop
      </Link>

      <div className="mt-4 grid grid-cols-1 gap-8 md:grid-cols-2">
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
          {item.image_url ? (
            <img src={item.image_url} alt={item.name} className="h-80 w-full object-cover" />
          ) : (
            <div className="h-80 w-full bg-gray-100" />
          )}
        </div>

        <div>
          {item.category && (
            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
              {item.category}
            </p>
          )}
          <h1 className="mt-1 text-2xl font-semibold text-gray-900">{item.name}</h1>
          <p className="mt-3 text-xl font-semibold text-brand-600">
            {item.price != null ? `$${item.price.toFixed(2)}` : 'Price on request'}
          </p>

          {item.description && (
            <p className="mt-4 whitespace-pre-line text-sm text-gray-600">{item.description}</p>
          )}

          <div className="mt-4 text-sm">
            {item.stock_quantity != null ? (
              outOfStock ? (
                <span className="font-medium text-red-600">Out of stock</span>
              ) : (
                <span className="text-gray-500">{item.stock_quantity} in stock</span>
              )
            ) : null}
          </div>

          <div className="mt-6 flex gap-3">
            <button
              onClick={handleAddToCart}
              disabled={item.price == null || outOfStock}
              className="rounded-lg bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {added ? 'Added ✓' : 'Add to cart'}
            </button>
            <button
              onClick={() => navigate('/cart')}
              className="rounded-lg border border-gray-300 px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Go to cart
            </button>
          </div>
        </div>
      </div>
    </Layout>
  )
}
