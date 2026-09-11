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
  const [parentItem, setParentItem] = useState(null)
  const [variants, setVariants] = useState([])
  const [selectedVariant, setSelectedVariant] = useState(null)
  const [gallery, setGallery] = useState([])
  const [activeImage, setActiveImage] = useState(0)
  const [error, setError] = useState(null)
  const [added, setAdded] = useState(false)

  // Load the item itself, plus (if it has variant siblings either as
  // the base or as one variant among several) the whole group and the
  // canonical parent to show as the product name/description.
  useEffect(() => {
    let cancelled = false
    setError(null)
    setItem(null)
    setParentItem(null)
    setVariants([])
    setSelectedVariant(null)
    setActiveImage(0)

    api
      .get(`/items/${id}`)
      .then(async (loaded) => {
        if (cancelled) return
        setItem(loaded)
        const groupId = loaded.variant_parent_id ?? loaded.id

        const [parent, siblingVariants] = await Promise.all([
          loaded.variant_parent_id ? api.get(`/items/${groupId}`) : Promise.resolve(loaded),
          api.get(`/items/${groupId}/variants`),
        ])
        if (cancelled) return
        setParentItem(parent)
        setVariants(siblingVariants)
        setSelectedVariant(loaded.variant_parent_id ? loaded : siblingVariants[0] || null)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load this product.')
      })

    return () => {
      cancelled = true
    }
  }, [id])

  // Whichever item is actually being sold right now — the selected
  // variant if this product has any, otherwise the item itself.
  const displayed = variants.length > 0 ? selectedVariant : item

  useEffect(() => {
    if (!displayed) return
    api
      .get(`/items/${displayed.id}/images`)
      .then(setGallery)
      .catch(() => setGallery([]))
  }, [displayed?.id])

  function handleAddToCart() {
    addToCart(displayed)
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

  if (!item || !displayed) {
    return (
      <Layout>
        <p className="text-gray-500">Loading…</p>
      </Layout>
    )
  }

  const outOfStock = displayed.stock_quantity != null && displayed.stock_quantity <= 0
  const images = [displayed.image_url, ...gallery].filter(Boolean)

  return (
    <Layout>
      <Link to="/" className="text-sm text-brand-600 hover:underline">
        ← Back to shop
      </Link>

      <div className="mt-4 grid grid-cols-1 gap-8 md:grid-cols-2">
        <div>
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
            {images.length > 0 ? (
              <img
                src={images[Math.min(activeImage, images.length - 1)]}
                alt={parentItem?.name || displayed.name}
                className="h-80 w-full object-cover"
              />
            ) : (
              <div className="h-80 w-full bg-gray-100" />
            )}
          </div>
          {images.length > 1 && (
            <div className="mt-2 flex gap-2">
              {images.map((src, i) => (
                <button
                  key={src + i}
                  onClick={() => setActiveImage(i)}
                  className={`h-16 w-16 shrink-0 overflow-hidden rounded-lg border-2 ${
                    i === activeImage ? 'border-brand-500' : 'border-transparent'
                  }`}
                >
                  <img src={src} alt="" className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div>
          {parentItem?.category && (
            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
              {parentItem.category}
            </p>
          )}
          <h1 className="mt-1 text-2xl font-semibold text-gray-900">{parentItem?.name}</h1>
          <p className="mt-3 text-xl font-semibold text-brand-600">
            {displayed.price != null ? `$${displayed.price.toFixed(2)}` : 'Price on request'}
          </p>

          {parentItem?.description && (
            <p className="mt-4 whitespace-pre-line text-sm text-gray-600">
              {parentItem.description}
            </p>
          )}

          {variants.length > 0 && (
            <div className="mt-4">
              <p className="mb-1.5 text-sm font-medium text-gray-700">Options</p>
              <div className="flex flex-wrap gap-2">
                {variants.map((variant) => (
                  <button
                    key={variant.id}
                    onClick={() => setSelectedVariant(variant)}
                    className={`rounded-lg border px-3 py-1.5 text-sm transition ${
                      selectedVariant?.id === variant.id
                        ? 'border-brand-500 bg-brand-50 font-medium text-brand-700'
                        : 'border-gray-300 text-gray-600 hover:border-gray-400'
                    }`}
                  >
                    {variant.variant_label || variant.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="mt-4 text-sm">
            {displayed.stock_quantity != null ? (
              outOfStock ? (
                <span className="font-medium text-red-600">Out of stock</span>
              ) : (
                <span className="text-gray-500">{displayed.stock_quantity} in stock</span>
              )
            ) : null}
          </div>

          <div className="mt-6 flex gap-3">
            <button
              onClick={handleAddToCart}
              disabled={displayed.price == null || outOfStock}
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
