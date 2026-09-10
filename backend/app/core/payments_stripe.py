"""
Stripe implementation of PaymentProvider (see core/payments.py for the
interface this satisfies). Kept in its own file, not payments.py, so
the base template's provider-agnostic file never imports a specific
vendor's SDK — a deployment that doesn't use Stripe never even
imports this module (see get_payment_provider() in payments.py).

metadata["payment_method_id"] is expected to be a Stripe PaymentMethod
id (looks like "pm_..."), created client-side by Stripe.js/Elements
from the card the customer typed in. The raw card number never
reaches this server — Stripe.js sends it directly to Stripe and hands
back only this token. That's the whole point of using Stripe rather
than handling card data ourselves: this codebase never touches a real
card number and therefore never falls under the heaviest PCI-DSS
requirements.

confirm=True below means Stripe attempts the charge immediately and
synchronously as part of creating the PaymentIntent — fine for a
simple card charge, but a deployment that later adds 3D Secure /
SCA-required cards will need to handle a "requires_action" status
here instead of treating anything short of "succeeded" as a hard
failure.
"""

import stripe

from app.core.payments import PaymentProvider, PaymentResult


class StripePaymentProvider(PaymentProvider):
    def __init__(self, secret_key: str):
        self._client = stripe.StripeClient(secret_key)

    async def charge(self, amount: float, currency: str, metadata: dict) -> PaymentResult:
        payment_method_id = metadata.get("payment_method_id")
        if not payment_method_id:
            return PaymentResult(
                success=False, reference=None, message="No card details were provided."
            )

        try:
            intent = await self._client.payment_intents.create_async(
                {
                    # Stripe wants amounts as an integer count of the
                    # currency's smallest unit (cents for USD) — not
                    # a float dollar amount.
                    "amount": round(amount * 100),
                    "currency": currency,
                    "payment_method": payment_method_id,
                    "confirm": True,
                    "automatic_payment_methods": {
                        "enabled": True,
                        "allow_redirects": "never",
                    },
                }
            )
        except stripe.StripeError as exc:
            return PaymentResult(
                success=False,
                reference=None,
                message=exc.user_message or "The card was declined.",
            )

        if intent.status != "succeeded":
            return PaymentResult(
                success=False,
                reference=intent.id,
                message=f"Payment not completed (status: {intent.status}).",
            )

        return PaymentResult(success=True, reference=intent.id, message=None)
