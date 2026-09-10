"""
Payment provider abstraction — the seam where a real processor
(Stripe, Square, PayPal, etc.) gets wired in later.

This base build deliberately does NOT integrate any specific
processor: which one a business wants is a deployment decision, not
a base-template decision, and hardcoding one vendor's SDK would make
every deployment of this template carry a dependency most of them
won't use. What every business DOES share is the shape of the
problem — "charge this amount, get back a reference" — so that's
what lives here.

PaymentProvider is the interface. ManualPaymentProvider is the
default implementation, and it does NOT contact any external service
— it mirrors today's actual behavior (payment_method is just a
record of how money moved, nothing is actually charged). This means
the base build works correctly with zero configuration, and swapping
in a real processor later means writing one new class that satisfies
this same interface, not restructuring the transaction flow or the
database.

To integrate a real processor:
    1. Create e.g. StripePaymentProvider(PaymentProvider) in a new
       file, implementing charge() to call the real API — see
       core/payments_stripe.py for exactly this, already done for
       Stripe specifically.
    2. Swap the provider instance in wherever get_payment_provider()
       is used — get_payment_provider() itself already does this,
       switching to Stripe automatically once stripe_secret_key is set.
    3. Store real API keys via app.core.config.settings, never
       hardcoded.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PaymentResult:
    success: bool
    reference: str | None  # the processor's charge/payment id, for Transaction.payment_reference
    message: str | None = None


class PaymentProvider(ABC):
    @abstractmethod
    async def charge(self, amount: float, currency: str, metadata: dict) -> PaymentResult:
        """Attempt to charge `amount` in `currency`. `metadata` is
        provider-specific context (e.g. a Stripe payment method id) —
        the base build doesn't define its shape since that's entirely
        dependent on which real processor gets wired in."""
        raise NotImplementedError


class ManualPaymentProvider(PaymentProvider):
    """Default provider — does not contact any external service.
    Represents payment methods that are recorded, not processed
    in-app: cash handed over, a card run on a separate physical
    terminal, a bank transfer confirmed manually. This is today's
    actual behavior for every transaction in the base build."""

    async def charge(self, amount: float, currency: str, metadata: dict) -> PaymentResult:
        return PaymentResult(success=True, reference=None, message="Recorded manually — not processed by this system.")


def get_payment_provider() -> PaymentProvider:
    """Single point of configuration for which provider is active.
    Falls back to ManualPaymentProvider with zero config — a
    deployment that never sets stripe_secret_key behaves exactly as
    before. Set stripe_secret_key (a sk_test_... key while developing,
    sk_live_... only once actually taking real payments) to switch to
    real Stripe charging. See api/transactions.py for where this
    actually gets called."""
    from app.core.config import settings

    if settings.stripe_secret_key:
        from app.core.payments_stripe import StripePaymentProvider

        return StripePaymentProvider(settings.stripe_secret_key)
    return ManualPaymentProvider()
