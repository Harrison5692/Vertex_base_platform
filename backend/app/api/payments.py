"""
Public endpoint telling the frontend whether real card charging is
configured for this deployment, and if so, which publishable key to
use. The publishable key is safe to expose — Stripe's own SDK is
designed to ship it to the browser; it can only ever create tokens,
never charge anything by itself. The secret key never leaves the
backend (see core/payments_stripe.py).
"""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/config")
async def get_payments_config():
    return {
        "stripe_enabled": bool(settings.stripe_secret_key),
        "stripe_publishable_key": settings.stripe_publishable_key,
    }
