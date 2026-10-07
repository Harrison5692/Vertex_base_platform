import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CardElement, Elements } from '@stripe/react-stripe-js'
import { loadStripe } from '@stripe/stripe-js'
import AuthModal from '../components/AuthModal'
import Layout from '../components/Layout'
import StripeCardField from '../components/StripeCardField'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useCart } from '../lib/cart'
import { useClientConfig } from '../lib/clientConfig'

const PAYMENT_METHODS = ['cash', 'card', 'bank_transfer', 'other']

// Matches backend app/core/pricing.py US_STATES — the server rejects
// anything else, so a dropdown avoids "Texas" vs "TX" typos entirely.
const US_STATES = [
  'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL', 'GA', 'HI', 'ID', 'IL',
  'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE',
  'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD',
  'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
]

const EMPTY_SHIPPING = {
  shipping_name: '',
  shipping_line1: '',
  shipping_line2: '',
  shipping_city: '',
  shipping_state: '',
  shipping_postal_code: '',
  shipping_country: 'US',
  shipping_phone: '',
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const US_ZIP_RE = /^\d{5}(-\d{4})?$/

const REQUIRED_SHIPPING = [
  ['shipping_name', 'Full name'],
  ['shipping_line1', 'Address line 1'],
  ['shipping_city', 'City'],
  ['shipping_state', 'State'],
  ['shipping_postal_code', 'ZIP code'],
]

const INPUT_BASE =
  'w-full rounded-lg border px-3 py-1.5 text-sm focus:outline-none disabled:bg-gray-50 disabled:text-gray-500'

function inputClass(hasError) {
  return `${INPUT_BASE} ${
    hasError
      ? 'border-red-500 focus:border-red-500 focus:ring-1 focus:ring-red-500'
      : 'border-gray-300 focus:border-brand-500'
  }`
}

function FieldError({ message }) {
  if (!message) return null
  return <p className="mt-0.5 text-xs text-red-600">{message}</p>
}

function CartLine({ line, onUpdateQuantity, onRemove }) {
  return (
    <li className="flex items-center gap-3 py-3">
      {line.image_url ? (
        <img src={line.image_url} alt={line.name} className="h-14 w-14 rounded-lg object-cover" />
      ) : (
        <div className="h-14 w-14 shrink-0 rounded-lg bg-gray-100" />
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-gray-900">{line.name}</p>
        <p className="text-sm text-gray-500">${line.unit_price.toFixed(2)} each</p>
      </div>
      <input
        type="number"
        min="1"
        value={line.quantity}
        onChange={(e) => onUpdateQuantity(line.item_id, e.target.value)}
        className="w-14 rounded border border-gray-300 px-1 py-1 text-center text-sm"
      />
      <span className="w-16 text-right text-sm font-medium text-gray-900">
        ${(line.unit_price * line.quantity).toFixed(2)}
      </span>
      <button onClick={() => onRemove(line.item_id)} className="text-gray-400 hover:text-red-600">
        ✕
      </button>
    </li>
  )
}

/** Staff-only: a search + quick-add grid for ringing up an in-person
 * sale. A customer checking out online never needs this — they add
 * items by browsing the storefront (Home / product pages) — so it's
 * gated to isStaff entirely, not shown as a general "keep shopping"
 * widget. */
function StaffQuickAdd({ onAddToCart }) {
  const [items, setItems] = useState([])
  const [search, setSearch] = useState('')

  useEffect(() => {
    const params = new URLSearchParams()
    if (search) params.set('q', search)
    const qs = params.toString()
    api
      .get(`/items/${qs ? `?${qs}` : ''}`)
      .then(setItems)
      .catch(() => setItems([]))
  }, [search])

  return (
    <div className="lg:col-span-2">
      <h2 className="font-semibold text-gray-900">Ring up a sale</h2>
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search items…"
        className="mb-3 mt-2 w-full max-w-sm rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => onAddToCart(item)}
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
        {items.length === 0 && <p className="col-span-full text-gray-400">No items found.</p>}
      </div>
    </div>
  )
}

export default function Cart() {
  const { user } = useAuth()
  const config = useClientConfig()
  const isStaff = user && user.tier >= 2
  const { cart, addToCart, updateQuantity, removeFromCart, clearCart } = useCart()
  const [paymentMethod, setPaymentMethod] = useState('card')
  // Tax is config-driven, not customer-editable — an earlier version of
  // this page let ANY caller type their own tax amount, which meant a
  // customer could just enter 0. Staff can still override it manually
  // (e.g. a tax-exempt sale); everyone else gets the deployment's
  // configured rate with no way to change it client-side.
  const [taxOverride, setTaxOverride] = useState(null)
  const [guestLabel, setGuestLabel] = useState('')
  // Guest checkout: no account required to buy, but an email is
  // required so the order confirmation has somewhere to go. Only
  // relevant when nobody's logged in — a logged-in customer's own
  // account email covers this already.
  const [guestEmail, setGuestEmail] = useState('')
  // Shipping is a retail-vertical concept: a staff-run walk-in sale
  // has no destination, so this only applies to a non-staff (online)
  // checkout and is required there before submitting.
  const [shipping, setShipping] = useState(EMPTY_SHIPPING)
  // Server-computed subtotal/shipping/tax/total for the current cart
  // and destination (POST /transactions/quote) — the exact code path
  // checkout charges with, so what's shown is what's charged.
  const [rawQuote, setQuote] = useState(null)
  const [quoteError, setQuoteError] = useState(null)
  // Per-field problems ({shipping_city: 'City is required.'}), shown
  // under each input and as one summary line — so a customer always
  // knows exactly which box to fix, instead of a greyed-out button.
  const [fieldErrors, setFieldErrors] = useState({})
  // Promo code: codeInput is what's typed, appliedCode is what's sent
  // with the quote/checkout once the customer presses Apply.
  const [codeInput, setCodeInput] = useState('')
  const [appliedCode, setAppliedCode] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [receipt, setReceipt] = useState(null)
  // Snapshot of the cart at the moment of submit, kept only so the
  // receipt screen can show names/thumbnails — the server's
  // TransactionWithLines response doesn't carry item names, and by
  // the time the receipt renders, `cart` itself has been cleared.
  const [receiptItems, setReceiptItems] = useState([])
  const [showAuth, setShowAuth] = useState(false)

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

  // Staff run walk-in POS sales (no destination); anyone else is
  // placing an online order and needs a real shipping address.
  const needsShipping = !isStaff
  const allowedCountries = config.shipping?.allowed_countries ?? ['US']

  useEffect(() => {
    if (cart.length === 0) return
    let cancelled = false
    api
      .post('/transactions/quote', {
        lines: cart.map((line) => ({
          item_id: line.item_id,
          quantity: line.quantity,
          unit_price: line.unit_price,
        })),
        online: needsShipping,
        shipping_country: shipping.shipping_country || null,
        shipping_state: shipping.shipping_state || null,
        tax_amount: isStaff && taxOverride != null ? taxOverride : null,
        discount_code: appliedCode,
      })
      .then((q) => {
        if (!cancelled) {
          setQuote(q)
          setQuoteError(null)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setQuote(null)
          setQuoteError(err?.detail || 'Could not calculate totals.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [
    cart,
    needsShipping,
    isStaff,
    taxOverride,
    appliedCode,
    shipping.shipping_country,
    shipping.shipping_state,
  ])

  // An empty cart shows no quote (rather than resetting state inside
  // the effect, which the React hooks lint rule flags).
  const quote = cart.length > 0 ? rawQuote : null
  const subtotal = quote?.subtotal ?? cart.reduce((sum, l) => sum + l.unit_price * l.quantity, 0)
  const total = quote?.total
  function validateCheckout() {
    const errors = {}
    // Don't let someone check out believing a code applied when it
    // didn't — make them fix or clear it first.
    if (appliedCode && quote?.discount_code_error) {
      errors.discount_code = `${quote.discount_code_error} Remove it or try another code.`
    }
    if (needsShipping) {
      if (!user) {
        if (!guestEmail.trim()) errors.guest_email = 'Email is required for your receipt.'
        else if (!EMAIL_RE.test(guestEmail.trim()))
          errors.guest_email = 'Enter a valid email address (like you@example.com).'
      }
      for (const [field, label] of REQUIRED_SHIPPING) {
        if (!String(shipping[field] ?? '').trim()) errors[field] = `${label} is required.`
      }
      if (!errors.shipping_line1 && !/\d/.test(shipping.shipping_line1)) {
        errors.shipping_line1 = 'Include the street number (like 123 Main St).'
      }
      if (
        !errors.shipping_postal_code &&
        shipping.shipping_country === 'US' &&
        !US_ZIP_RE.test(shipping.shipping_postal_code.trim())
      ) {
        errors.shipping_postal_code = 'Enter a 5-digit ZIP code (like 77002).'
      }
    }
    return errors
  }

  function clearFieldError(field) {
    setFieldErrors((prev) => {
      const next = { ...prev }
      delete next[field]
      return next
    })
  }

  function updateShipping(field, value) {
    setShipping((prev) => ({ ...prev, [field]: value }))
    if (fieldErrors[field]) clearFieldError(field)
  }

  // Online order paying by card, with Stripe actually configured: this
  // deployment is meant to charge for real.
  const useStripeCharge = needsShipping && paymentMethod === 'card' && stripeEnabled

  async function handleCheckout() {
    if (cart.length === 0) return
    const errors = validateCheckout()
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) {
      setError(null)
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
        ...(isStaff && taxOverride != null ? { tax_amount: taxOverride } : {}),
        lines: cart.map((line) => ({
          item_id: line.item_id,
          quantity: line.quantity,
          unit_price: line.unit_price,
        })),
        ...(needsShipping ? shipping : {}),
        ...(!user && guestEmail ? { guest_email: guestEmail } : {}),
        ...(stripePaymentMethodId ? { stripe_payment_method_id: stripePaymentMethodId } : {}),
        ...(appliedCode ? { discount_code: appliedCode } : {}),
      })
      setReceipt(result)
      setReceiptItems(cart)
      clearCart()
      setGuestLabel('')
      setGuestEmail('')
      setTaxOverride(null)
      setShipping(EMPTY_SHIPPING)
      setCodeInput('')
      setAppliedCode(null)
    } catch (err) {
      // A declined card (402) gets its actual reason from the server;
      // anything else falls back to the generic message as before.
      // A field the server rejected gets outlined just like a
      // client-side one; anything else shows its actual reason.
      if (err?.fieldErrors && Object.keys(err.fieldErrors).length > 0) {
        setFieldErrors(err.fieldErrors)
        setError(null)
      } else {
        setError(err?.detail || 'Checkout failed — please try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (receipt) {
    const itemsById = Object.fromEntries(receiptItems.map((line) => [line.item_id, line]))
    return (
      <Layout>
        <div className="mx-auto max-w-md rounded-xl border border-gray-200 bg-white p-6 text-center shadow-sm">
          <p className="text-sm font-medium text-green-600">
            {needsShipping ? 'Order placed' : 'Sale completed'}
          </p>
          <p className="mt-2 text-3xl font-bold text-gray-900">${receipt.total.toFixed(2)}</p>
          <p className="mt-1 text-sm text-gray-500">Transaction #{receipt.id}</p>
          <ul className="mt-4 divide-y divide-gray-100 text-left text-sm">
            {receipt.lines.map((line) => {
              const known = itemsById[line.item_id]
              return (
                <li key={line.id} className="flex items-center gap-3 py-2">
                  {known?.image_url ? (
                    <img
                      src={known.image_url}
                      alt={known.name}
                      className="h-10 w-10 rounded-lg object-cover"
                    />
                  ) : (
                    <div className="h-10 w-10 shrink-0 rounded-lg bg-gray-100" />
                  )}
                  <span className="flex-1 truncate">
                    {line.quantity}× {known?.name || `Item #${line.item_id}`}
                  </span>
                  <span>${line.line_total.toFixed(2)}</span>
                </li>
              )
            })}
          </ul>
          <div className="mt-3 space-y-1 border-t border-gray-100 pt-3 text-left text-sm text-gray-500">
            <div className="flex justify-between">
              <span>Subtotal</span>
              <span>${receipt.subtotal.toFixed(2)}</span>
            </div>
            {receipt.discount_amount > 0 && (
              <div className="flex justify-between text-green-700">
                <span>Discount ({receipt.discount_code})</span>
                <span>−${receipt.discount_amount.toFixed(2)}</span>
              </div>
            )}
            {receipt.shipping_amount != null && (
              <div className="flex justify-between">
                <span>Shipping</span>
                <span>
                  {receipt.shipping_amount === 0 ? 'Free' : `$${receipt.shipping_amount.toFixed(2)}`}
                </span>
              </div>
            )}
            <div className="flex justify-between">
              <span>Tax</span>
              <span>${receipt.tax_amount.toFixed(2)}</span>
            </div>
          </div>
          <div className="mt-5 flex gap-2">
            <Link
              to="/"
              className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Continue shopping
            </Link>
            <button
              onClick={() => setReceipt(null)}
              className="flex-1 rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600"
            >
              New sale
            </button>
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Cart</h1>
        <Link to="/" className="text-sm text-brand-600 hover:underline">
          ← Continue shopping
        </Link>
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <div className={`mt-6 grid grid-cols-1 gap-6 ${isStaff ? 'lg:grid-cols-3' : 'mx-auto max-w-lg'}`}>
        {isStaff && <StaffQuickAdd onAddToCart={addToCart} />}

        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          {cart.length === 0 ? (
            <p className="text-sm text-gray-400">Your cart is empty.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {cart.map((line) => (
                <CartLine
                  key={line.item_id}
                  line={line}
                  onUpdateQuantity={updateQuantity}
                  onRemove={removeFromCart}
                />
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

          {!user && needsShipping && (
            <div className="mt-4 border-t border-gray-100 pt-3">
              <label className="block text-sm">
                <span className="mb-1 block text-gray-600">Email (for your receipt)</span>
                <input
                  type="email"
                  value={guestEmail}
                  onChange={(e) => {
                    setGuestEmail(e.target.value)
                    if (fieldErrors.guest_email) clearFieldError('guest_email')
                  }}
                  placeholder="you@example.com"
                  className={inputClass(fieldErrors.guest_email)}
                />
                <FieldError message={fieldErrors.guest_email} />
              </label>
              <button
                type="button"
                onClick={() => setShowAuth(true)}
                className="mt-1.5 text-xs text-brand-600 hover:underline"
              >
                Already have an account? Sign in
              </button>
            </div>
          )}

          {needsShipping && (
            <div className="mt-4 space-y-2 border-t border-gray-100 pt-3">
              <p className="text-sm font-medium text-gray-700">Shipping address</p>
              <div>
                <input
                  value={shipping.shipping_name}
                  onChange={(e) => updateShipping('shipping_name', e.target.value)}
                  placeholder="Full name"
                  autoComplete="name"
                  className={inputClass(fieldErrors.shipping_name)}
                />
                <FieldError message={fieldErrors.shipping_name} />
              </div>
              <div>
                <input
                  value={shipping.shipping_line1}
                  onChange={(e) => updateShipping('shipping_line1', e.target.value)}
                  placeholder="Address line 1"
                  autoComplete="address-line1"
                  className={inputClass(fieldErrors.shipping_line1)}
                />
                <FieldError message={fieldErrors.shipping_line1} />
              </div>
              <input
                value={shipping.shipping_line2}
                onChange={(e) => updateShipping('shipping_line2', e.target.value)}
                placeholder="Address line 2 (optional)"
                autoComplete="address-line2"
                className={inputClass(false)}
              />
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <input
                    value={shipping.shipping_city}
                    onChange={(e) => updateShipping('shipping_city', e.target.value)}
                    placeholder="City"
                    autoComplete="address-level2"
                    className={inputClass(fieldErrors.shipping_city)}
                  />
                  <FieldError message={fieldErrors.shipping_city} />
                </div>
                <div>
                  <select
                    value={shipping.shipping_state}
                    onChange={(e) => updateShipping('shipping_state', e.target.value)}
                    autoComplete="address-level1"
                    className={inputClass(fieldErrors.shipping_state)}
                  >
                    <option value="">State</option>
                    {US_STATES.map((code) => (
                      <option key={code} value={code}>
                        {code}
                      </option>
                    ))}
                  </select>
                  <FieldError message={fieldErrors.shipping_state} />
                </div>
                <div>
                  <input
                    value={shipping.shipping_postal_code}
                    onChange={(e) => updateShipping('shipping_postal_code', e.target.value)}
                    placeholder="ZIP code"
                    inputMode="numeric"
                    autoComplete="postal-code"
                    className={inputClass(fieldErrors.shipping_postal_code)}
                  />
                  <FieldError message={fieldErrors.shipping_postal_code} />
                </div>
                <div>
                  <select
                    value={shipping.shipping_country}
                    onChange={(e) => updateShipping('shipping_country', e.target.value)}
                    disabled={allowedCountries.length === 1}
                    className={inputClass(fieldErrors.shipping_country)}
                  >
                    {allowedCountries.map((code) => (
                      <option key={code} value={code}>
                        {code === 'US' ? 'United States' : code}
                      </option>
                    ))}
                  </select>
                  <FieldError message={fieldErrors.shipping_country} />
                </div>
              </div>
              <input
                value={shipping.shipping_phone}
                onChange={(e) => updateShipping('shipping_phone', e.target.value)}
                placeholder="Phone (optional)"
                autoComplete="tel"
                className={inputClass(false)}
              />
            </div>
          )}

          {(isStaff || !stripeEnabled) && (
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
          )}

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
                value={taxOverride ?? (quote ? quote.tax.toFixed(2) : '')}
                onChange={(e) => setTaxOverride(Number(e.target.value))}
                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
              />
            </label>
          ) : null}

          <div className="mt-4 border-t border-gray-100 pt-3">
            <label className="block text-sm">
              <span className="mb-1 block text-gray-600">Discount code</span>
              <div className="flex gap-2">
                <input
                  value={codeInput}
                  onChange={(e) => {
                    setCodeInput(e.target.value)
                    if (fieldErrors.discount_code) clearFieldError('discount_code')
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') setAppliedCode(codeInput.trim() || null)
                  }}
                  placeholder="Enter code"
                  disabled={!!appliedCode}
                  className={`${inputClass(
                    fieldErrors.discount_code || (appliedCode && quote?.discount_code_error),
                  )} uppercase`}
                />
                {appliedCode ? (
                  <button
                    type="button"
                    onClick={() => {
                      setAppliedCode(null)
                      setCodeInput('')
                    }}
                    className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    Remove
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setAppliedCode(codeInput.trim() || null)}
                    disabled={!codeInput.trim()}
                    className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                  >
                    Apply
                  </button>
                )}
              </div>
            </label>
            <FieldError
              message={fieldErrors.discount_code || (appliedCode && quote?.discount_code_error)}
            />
          </div>

          <div className="mt-4 space-y-1 border-t border-gray-100 pt-3 text-sm">
            <div className="flex justify-between text-gray-500">
              <span>Subtotal</span>
              <span>${subtotal.toFixed(2)}</span>
            </div>
            {quote?.discount > 0 && (
              <div className="flex justify-between text-green-700">
                <span>Discount ({appliedCode?.toUpperCase()})</span>
                <span>−${quote.discount.toFixed(2)}</span>
              </div>
            )}
            {needsShipping && (
              <div className="flex justify-between text-gray-500">
                <span>Shipping</span>
                <span>
                  {quote == null ? '—' : quote.shipping === 0 ? 'Free' : `$${quote.shipping.toFixed(2)}`}
                </span>
              </div>
            )}
            <div className="flex justify-between text-gray-500">
              <span>Tax</span>
              <span>
                {quote == null
                  ? '—'
                  : needsShipping && !shipping.shipping_state
                    ? 'Select a state'
                    : `$${quote.tax.toFixed(2)}`}
              </span>
            </div>
            <div className="flex justify-between font-semibold text-gray-900">
              <span>Total</span>
              <span>{total == null ? '—' : `$${total.toFixed(2)}`}</span>
            </div>
            {needsShipping && quote?.free_shipping_remaining != null && (
              <p className="pt-1 text-xs text-brand-600">
                Add ${quote.free_shipping_remaining.toFixed(2)} more for free shipping
              </p>
            )}
            {quoteError && <p className="pt-1 text-xs text-red-600">{quoteError}</p>}
          </div>

          {Object.keys(fieldErrors).length > 0 && (
            <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              Please fix: {Object.values(fieldErrors).join(' ')}
            </p>
          )}

          {/* Deliberately NOT disabled for missing fields — clicking runs
              validateCheckout() and shows exactly which fields need
              attention, instead of a silently greyed-out button. */}
          <button
            onClick={handleCheckout}
            disabled={
              cart.length === 0 || submitting || quote == null || (useStripeCharge && !stripePromise)
            }
            className="mt-4 w-full rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:opacity-50"
          >
            {submitting
              ? 'Processing…'
              : useStripeCharge
                ? `Pay ${total == null ? '' : `$${total.toFixed(2)}`}`
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
