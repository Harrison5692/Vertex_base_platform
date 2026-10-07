"""
Promo-code rules — which code applies, and how much it takes off.

check_discount() is pure (no database) so every rule is unit-tested
directly; resolve_discount() is the thin database wrapper checkout and
the quote endpoint share. Every rejection raises DiscountError with a
message written for the customer — it's shown under the code box as-is.
"""

from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.pricing import cents
from app.models.discount_code import DiscountCode, DiscountKind


class DiscountError(ValueError):
    pass


def normalize_code(code: str | None) -> str | None:
    if code is None:
        return None
    code = code.strip().upper()
    return code or None


def check_discount(dc: DiscountCode | None, subtotal: float, now: datetime) -> float:
    """Returns the dollar amount off, or raises DiscountError."""
    if dc is None or not dc.is_active:
        raise DiscountError("That code isn't valid.")
    if dc.starts_at is not None and now < dc.starts_at:
        raise DiscountError("That code isn't active yet.")
    if dc.expires_at is not None and now >= dc.expires_at:
        raise DiscountError("That code has expired.")
    if dc.max_uses is not None and dc.uses_count >= dc.max_uses:
        raise DiscountError("That code has reached its usage limit.")
    if dc.min_subtotal is not None and subtotal < dc.min_subtotal:
        raise DiscountError(f"That code needs an order of at least ${dc.min_subtotal:.2f}.")
    if dc.kind == DiscountKind.percent:
        amount = subtotal * dc.value / 100
    else:
        amount = dc.value
    return cents(min(amount, subtotal))


async def resolve_discount(
    session: AsyncSession, code: str | None, subtotal: float, *, lock: bool
) -> tuple[DiscountCode | None, float]:
    """(None, 0.0) when no code was entered. lock=True (checkout) takes
    a row lock so the usage count can't be overshot concurrently."""
    normalized = normalize_code(code)
    if normalized is None:
        return None, 0.0
    query = select(DiscountCode).where(DiscountCode.code == normalized)
    if lock:
        query = query.with_for_update()
    dc = (await session.exec(query)).first()
    amount = check_discount(dc, subtotal, datetime.utcnow())
    return dc, amount
