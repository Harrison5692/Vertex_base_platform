"""
Shared stock-related helpers used by both the items API (manual edits
to stock_quantity) and the transactions API (stock decremented as a
side effect of a sale). Lives here rather than in either router so
neither has to import a "private" function from the other.
"""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.account import Account
from app.models.item import Item
from app.models.notification import Notification


async def maybe_notify_low_stock(
    session: AsyncSession, item: Item, previous_stock: int | None, current_account_id: int | None
) -> None:
    """Fires a notification to every active staff/admin account when an
    item's stock crosses AT OR BELOW its configured threshold. Only
    fires on the actual crossing (previous stock was above threshold,
    or the item is brand new) — not on every unrelated edit/sale made
    while stock happens to already be low, which would spam the same
    alert repeatedly. No-ops entirely if low_stock_threshold isn't set
    — this feature is opt-in per item, not forced on every deployment."""
    if item.low_stock_threshold is None or item.stock_quantity is None:
        return
    if item.stock_quantity > item.low_stock_threshold:
        return
    if previous_stock is not None and previous_stock <= item.low_stock_threshold:
        return  # already was below threshold — don't re-alert on unrelated edits/sales

    result = await session.exec(
        select(Account).where(Account.tier >= 2, Account.is_active == True)  # noqa: E712
    )
    for staff in result.all():
        session.add(
            Notification(
                account_id=staff.id,
                message=f"Low stock: '{item.name}' at {item.stock_quantity} "
                f"(threshold {item.low_stock_threshold})",
                created_by=current_account_id,
            )
        )
