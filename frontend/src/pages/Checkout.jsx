import { useCallback, useEffect, useRef, useState } from 'react'
import { CardElement, Elements } from '@stripe/react-stripe-js'
import { loadStripe } from '@stripe/stripe-js'
import AuthModal from '../components/AuthModal'
import Layout from '../components/Layout'
import StripeCardField from '../components/StripeCardField'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useClientConfig } from '../lib/clientConfig'

const PAYMENT_METHODS = ['cash', 'card', 'bank_transfer', 'other']
const CART_KEY = 'vertex_cart'

function loadCart() {
  try {
    const raw = localStorage.getItem(CART_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export default function Checkout() {
  const { user } = useAuth()
  const config = useClientConfig()
  const isStaff = user && user.tier >= 2
  const [items, setItems] = useState([])
  const [cart, setCart] = useState(loadCart)
  const [paymentMethod, setPaymentMethod] = useState('card')
  // Tax is config-driven, not customer-editable — an earlier version of
  // this page let ANY caller type their own tax amount, which meant a
  // customer could just enter 0. Staff can still override it manually
  // (e.g. a tax-exempt sale); everyone else gets the deployment's
  // configured rate with no way to change it client-side.
  const [taxOverride, setTaxOverride] = useState(null)
  const [guestLabel, setGuestLabel] = useState('')
  // Shipping is a retail-vertical concept: a staff-run walk-in sale
  // has no destination, so this only applies to a non-staff (online)
  // checkout and is required there before submitting.
  const [shipping, setShipping] = useState({
    shipping_name: '',
    shipping_line1: '',
    shipping_line2: '',
    shipping_city: '',
    shipping_state: '',
    shipping_postal_code: '',
    shipping_country: '',
    shipping_phone: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [receipt, setReceipt] = useState(null)
  const [showAuth, setShowAuth] = useState(false)
  const [search, setSearch] = useState('')

  // Stripe is entirely optional per-deployment (see /payments/config)
  // — stripePromise stays null, and the card field never renders,
  // for a deployment that hasn't set STRIPE_SECRET_KEY. stripeHandle
  // holds the live stripe/elements objects once StripeCardField
  // (which lives inside <Elements>, unlike this component) reports
  // them up, so handleCheckout can tokenize the card at submit time.
  const [stripePromise, setStripePromise] = useState(null)
  const [stripeEnabled, setStripeEnabled] = useState(false)
  const stripeHandle = useRef({ stripe: null, elements: null })
  const handleStripeReady = useCallback((stripe, elements) => {
    stripeHandle.current = { stripe, elements }
  }, [])

  useEffect(() => {
    api
      .get('/payments/config')
      .then((cfg) => {
        if (cfg.stripe_enabled && cfg.stripe_publishable_key) {
          setStripePromise(loadStripe(cfg.stripe_publishable_key))
          setStripeEnabled(true)
        }
      })
      .catch(() => {}) // Stripe just stays off — same as unconfigured
  }, [])

  useEffect(() => {
    const params = new URLSearchParams()
    if (search) params.set('q', search)
    const qs = params.toString()
    api
      .get(`/items/${qs ? `?${qs}` : ''}`)
      .then(setItems)
      .catch(() => setError('Could not load items.'))
  }, [search])

  useEffect(() => {
    localStorage.setItem(CART_KEY, JSON.stringify(cart))
  }, [cart])

  function addToCart(item) {
    setCart((prev) => {
      const existing = prev.find((line) => line.item_id === item.id)
      if (existing) {
        return prev.map((line) =>
          line.item_id === item.id ? { ...line, quantity: line.quantity + 1 } : line
        )
      }
      return [
        ...prev,
        { item_id: item.id, name: item.name, unit_price: item.price ?? 0, quantity: 1 },
      ]
    })
  }

  function updateQuantity(itemId, quantity) {
    const q = Math.max(1, Number(quantity) || 1)
    setCart((prev) => prev.map((l) => (l.item_id === itemId ? { ...l, quantity: q } : l)))
  }

  function removeLine(itemId) {
    setCart((prev) => prev.filter((l) => l.item_id !== itemId))
  }

  const subtotal = cart.reduce((sum, l) => sum + l.unit_price * l.quantity, 0)
  const configuredTax = subtotal * (config.tax_rate ?? 0)
  const tax = taxOverride ?? configuredTax
  const total = subtotal + tax

  // Staff run walk-in POS sales (no destination); anyone else is
  // placing an online order and needs a real shipping address.
  const needsShipping = !isStaff
  const shippingComplete =
    !needsShipping ||
    (shipping.shipping_name &&
      shipping.shipping_line1 &&
      shipping.shipping_city &&
      shipping.shipping_state &&
      shipping.shipping_postal_code &&
      shipping.shipping_country)

  // Online order paying by card, with Stripe actually configured: this
  // deployment is meant to charge for real.
  const useStripeCharge = needsShipping && paymentMethod === 'card' && stripeEnabled

  async function handleCheckout() {
    if (cart.length === 0) return
    if (!user) {
      setShowAuth(true)
      return
    }
    if (!shippingComplete) {
      setError('Enter a complete shipping address before checking out.')
      return
    }
    setSubmitting(true)
    setError(null)

    let stripePaymentMethodId = null
    if (useStripeCharge) {
      const { stripe, elements } = stripeHandle.current
      if (!stripe || !elements) {
        setError('Payment form is still loading — wait a moment and try again.')
        setSubmitting(false)
        return
      }
      const { paymentMethod: pm, error: stripeError } = await stripe.createPaymentMethod({
        type: 'card',
        card: elements.getElement(CardElement),
        billing_details: { name: shipping.shipping_name || undefined },
      })
      if (stripeError) {
        setError(stripeError.message)
        setSubmitting(false)
        return
      }
      stripePaymentMethodId = pm.id
    }

    try {
      const result = await api.post('/transactions/', {
        type: 'completed',
        payment_method: paymentMethod,
        guest_label: guestLabel || null,
        tax_amount: tax,
        lines: cart.map((l) => ({
          item_id: l.item_id,
          quantity: l.quantity,
          unit_price: l.unit_price,
        })),
        ...(needsShipping ? shipping : {}),
        ...(stripePaymentMethodId ? { stripe_payment_method_id: stripePaymentMethodId } : {}),
      })
      setReceipt(result)
      setCart([]) // also clears localStorage via the effect above
      setGuestLabel('')
      setTaxOverride(null)
      setShipping({
        shipping_name: '',
        shipping_line1: '',
        shipping_line2: '',
        shipping_city: '',
        shipping_state: '',
        shipping_postal_code: '',
        shipping_country: '',
        shipping_phone: '',
      })
    } catch (err) {
      // A declined card (402) gets its actual reason from the server;
      // anything else falls back to the generic message as before.
      setError(err?.detail || 'Checkout failed — one of the items may no longer exist.')
    } finally {
      setSubmitting(false)
    }
  }

  if (receipt) {
    return (
      <Layout>
        <div className="mx-auto max-w-md rounded-xl border border-gray-200 bg-white p-6 text-center shadow-sm">
          <p className="text-sm font-medium text-green-600">Sale completed</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">${receipt.total.toFixed(2)}</p>
          <p className="mt-1 text-sm text-gray-500">Transaction #{receipt.id}</p>
          <ul className="mt-4 divide-y divide-gray-100 text-left text-sm">
            {receipt.lines.map((l) => (
              <li key={l.id} className="flex justify-between py-2">
                <span>
                  {l.quantity}× item #{l.item_id}
                </span>
                <span>${l.line_total.toFixed(2)}</span>
              </li>
            ))}
          </ul>
          <button
            onClick={() => setReceipt(null)}
            className="mt-5 w-full rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600"
          >
            New sale
          </button>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <h1 className="text-2xl font-semibold text-gray-900">Checkout</h1>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search items…"
            className="mb-3 w-full max-w-sm rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {items.map((item) => (
              <button
                key={item.id}
                onClick={() => addToCart(item)}
                disabled={item.price == null}
                className="overflow-hidden rounded-xl border border-gray-200 bg-white text-left shadow-sm transition hover:border-brand-300 hover:shadow disabled:cursor-not-allowed disabled:opacity-50"
              >
                {item.image_url ? (
                  <img src={item.image_url} alt={item.name} className="h-28 w-full object-cover" />
                ) : (
                  <div className="h-28 w-full bg-gray-100" />
                )}
                <div className="p-3">
                  <p className="font-medium text-gray-900">{item.name}</p>
                  <p className="mt-1 text-sm text-gray-500">
                    {item.price != null ? `$${item.price.toFixed(2)}` : 'No price set'}
                  </p>
                </div>
              </button>
            ))}
            {items.length === 0 && (
              <p className="col-span-full text-gray-400">No items available.</p>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-gray-900">Cart</h2>

          {cart.length === 0 ? (
            <p className="mt-3 text-sm text-gray-400">Nothing added yet.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {cart.map((l) => (
                <li key={l.item_id} className="flex items-center justify-between text-sm">
                  <span className="flex-1 truncate">{l.name}</span>
                  <input
                    type="number"
                    min="1"
                    value={l.quantity}
                    onChange={(e) => updateQuantity(l.item_id, e.target.value)}
                    className="w-14 rounded border border-gray-300 px-1 py-0.5 text-center"
                  />
                  <span className="w-16 text-right">
                    ${(l.unit_price * l.quantity).toFixed(2)}
                  </span>
                  <button
                    onClick={() => removeLine(l.item_id)}
                    className="ml-2 text-gray-400 hover:text-red-600"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}

          {isStaff && (
            <label className="mt-4 block text-sm">
              <span className="mb-1 block text-gray-600">Guest label (optional)</span>
              <input
                value={guestLabel}
                onChange={(e) => setGuestLabel(e.target.value)}
                placeholder="Walk-in"
                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
              />
            </label>
          )}

          {needsShipping && (
            <div className="mt-4 space-y-2 border-t border-gray-100 pt-3">
              <p className="text-sm font-medium text-gray-700">Shipping address</p>
              <input
                value={shipping.shipping_name}
                onChange={(e) => setShipping({ ...shipping, shipping_name: e.target.value })}
                placeholder="Full name"
                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
              />
              <input
                value={shipping.shipping_line1}
                onChange={(e) => setShipping({ ...shipping, shipping_line1: e.target.value })}
                placeholder="Address line 1"
                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
              />
              <input
                value={shipping.shipping_line2}
                onChange={(e) => setShipping({ ...shipping, shipping_line2: e.target.value })}
                placeholder="Address line 2 (optional)"
                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
              />
              <div className="grid grid-cols-2 gap-2">
                <input
                  value={shipping.shipping_city}
                  onChange={(e) => setShipping({ ...shipping, shipping_city: e.target.value })}
                  placeholder="City"
                  className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
                />
                <input
                  value={shipping.shipping_state}
                  onChange={(e) => setShipping({ ...shipping, shipping_state: e.target.value })}
                  placeholder="State"
                  className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
                />
                <input
                  value={shipping.shipping_postal_code}
                  onChange={(e) =>
                    setShipping({ ...shipping, shipping_postal_code: e.target.value })
                  }
                  placeholder="Postal code"
                  className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
                />
                <input
                  value={shipping.shipping_country}
                  onChange={(e) => setShipping({ ...shipping, shipping_country: e.target.value })}
                  placeholder="Country"
                  className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
                />
              </div>
              <input
                value={shipping.shipping_phone}
                onChange={(e) => setShipping({ ...shipping, shipping_phone: e.target.value })}
                placeholder="Phone (optional)"
                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
              />
            </div>
          )}

          <label className="mt-3 block text-sm">
            <span className="mb-1 block text-gray-600">Payment method</span>
            <select
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
            >
              {PAYMENT_METHODS.map((m) => (
                <option key={m} value={m}>
                  {m.replace('_', ' ')}
                </option>
              ))}
            </select>
          </label>

          {useStripeCharge && stripePromise && (
            <div className="mt-3">
              <span className="mb-1 block text-sm text-gray-600">Card details</span>
              <Elements stripe={stripePromise}>
                <StripeCardField onReady={handleStripeReady} />
              </Elements>
            </div>
          )}

          {needsShipping && paymentMethod === 'card' && !stripeEnabled && (
            <p className="mt-2 text-xs text-gray-400">
              Card payments aren't configured for this store yet — this will record the sale
              without charging a card.
            </p>
          )}

          {isStaff ? (
            <label className="mt-3 block text-sm">
              <span className="mb-1 block text-gray-600">Tax (override)</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={taxOverride ?? configuredTax.toFixed(2)}
                onChange={(e) => setTaxOverride(Number(e.target.value))}
                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
              />
            </label>
          ) : (
            <p className="mt-3 text-xs text-gray-400">
              Tax calculated at {((config.tax_rate ?? 0) * 100).toFixed(2)}%
            </p>
          )}

          <div className="mt-4 space-y-1 border-t border-gray-100 pt-3 text-sm">
            <div className="flex justify-between text-gray-500">
              <span>Subtotal</span>
              <span>${subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-gray-500">
              <span>Tax</span>
              <span>${tax.toFixed(2)}</span>
            </div>
            <div className="flex justify-between font-semibold text-gray-900">
              <span>Total</span>
              <span>${total.toFixed(2)}</span>
            </div>
          </div>

          <button
            onClick={handleCheckout}
            disabled={
              cart.length === 0 ||
              submitting ||
              (user && !shippingComplete) ||
              (useStripeCharge && !stripePromise)
            }
            className="mt-4 w-full rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:opacity-50"
          >
            {submitting
              ? 'Processing…'
              : !user
                ? 'Sign in to complete sale'
                : useStripeCharge
                  ? `Pay $${total.toFixed(2)}`
                  : needsShipping
                    ? 'Place order'
                    : 'Complete sale'}
          </button>
        </div>
      </div>

      {showAuth && <AuthModal onClose={() => setShowAuth(false)} />}
    </Layout>
  )
}
