import { CardElement, useElements, useStripe } from '@stripe/react-stripe-js'
import { useEffect } from 'react'

/** Checkout itself renders outside <Elements> (it needs to work with
 * or without Stripe configured at all), so it can't call
 * useStripe()/useElements() directly. This component lives inside
 * <Elements> and hands those two objects up via onReady so Checkout
 * can tokenize the card at submit time. */
export default function StripeCardField({ onReady }) {
  const stripe = useStripe()
  const elements = useElements()

  useEffect(() => {
    onReady(stripe, elements)
  }, [stripe, elements, onReady])

  return (
    <div className="rounded-lg border border-gray-300 px-3 py-2.5">
      <CardElement
        options={{
          style: { base: { fontSize: '14px', color: '#111827', '::placeholder': { color: '#9ca3af' } } },
        }}
      />
    </div>
  )
}
