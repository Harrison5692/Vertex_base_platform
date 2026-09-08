"""
Public storefront newsletter/discount-code signup. No auth required
(this is deliberately lower-friction than registering an account),
rate-limited the same way login/password-reset are — an open POST
endpoint with no auth is an easy target for a scraper hammering it
with junk addresses.
"""

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.rate_limit import rate_limit
from app.db.session import get_session
from app.models.newsletter_signup import NewsletterSignup, NewsletterSignupCreate

router = APIRouter(prefix="/newsletter", tags=["newsletter"])


@router.post("/", status_code=201)
async def signup(
    body: NewsletterSignupCreate,
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit("newsletter_signup", max_attempts=5, window_seconds=300)),
):
    """Idempotent on purpose: re-submitting an email that's already
    subscribed returns the same success response rather than a 409 —
    a signup form has no reason to reveal whether an address is
    already on the list, and the person retrying just wants
    confirmation, not an error."""
    existing = await session.exec(
        select(NewsletterSignup).where(NewsletterSignup.email == body.email)
    )
    if existing.first():
        return {"status": "subscribed"}

    entry = NewsletterSignup(email=body.email)
    session.add(entry)
    await session.commit()
    return {"status": "subscribed"}
