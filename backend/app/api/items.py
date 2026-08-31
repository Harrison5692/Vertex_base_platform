"""
Example CRUD router — replace `Item` with your real entities.

Every client build starts by copying this file's pattern for each
of their actual domain objects (patients, orders, devices, whatever
the business runs on). Routes are auth-protected — copy that pattern
too for any real resource. Also copy the audit-log pattern: every
create/update/delete writes an AuditLog row alongside the change.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit import log_audit
from app.core.deps import get_current_account, require_min_tier
from app.db.session import get_session
from app.models.account import Account
from app.models.item import Item, ItemCreate, ItemRead, ItemUpdate
from app.models.notification import Notification

router = APIRouter(prefix="/items", tags=["items"])
# No router-level auth dependency — GET routes are intentionally public
# (browsing a catalog shouldn't require an account, same as any real
# storefront). POST/PATCH/DELETE below each carry their own
# require_min_tier(2), which pulls in get_current_account internally —
# so mutations are still fully auth-gated, just not via a blanket
# router-level requirement that would also lock out browsing.


async def _maybe_notify_low_stock(
    session: AsyncSession, item: Item, previous_stock: int | None, current_account_id: int
) -> None:
    """Fires a notification to every active staff/admin account when an
    item's stock crosses AT OR BELOW its configured threshold. Only
    fires on the actual crossing (previous stock was above threshold,
    or the item is brand new) — not on every unrelated edit made while
    stock happens to already be low, which would spam the same alert
    repeatedly. No-ops entirely if low_stock_threshold isn't set —
    this feature is opt-in per item, not forced on every deployment."""
    if item.low_stock_threshold is None or item.stock_quantity is None:
        return
    if item.stock_quantity > item.low_stock_threshold:
        return
    if previous_stock is not None and previous_stock <= item.low_stock_threshold:
        return  # already was below threshold — don't re-alert on unrelated edits

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


@router.get("/", response_model=list[ItemRead])
async def list_items(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Item))
    return result.all()


@router.post("/", response_model=ItemRead, status_code=201, dependencies=[Depends(require_min_tier(2))])
async def create_item(
    item_in: ItemCreate,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    item = Item.model_validate(item_in)
    session.add(item)
    await session.flush()  # assigns item.id without committing/expiring attributes

    await _maybe_notify_low_stock(session, item, previous_stock=None, current_account_id=current.id)

    await log_audit(
        session,
        table_name="item",
        record_id=item.id,
        action="create",
        changed_by=current.id,
        new_values=item.model_dump(),
    )
    await session.commit()
    await session.refresh(item)

    return item


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: int, session: AsyncSession = Depends(get_session)):
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/{item_id}", response_model=ItemRead, dependencies=[Depends(require_min_tier(2))])
async def update_item(
    item_id: int,
    item_in: ItemUpdate,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    old_values = item.model_dump()
    previous_stock = item.stock_quantity
    for field, value in item_in.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    session.add(item)

    await _maybe_notify_low_stock(
        session, item, previous_stock=previous_stock, current_account_id=current.id
    )

    await log_audit(
        session,
        table_name="item",
        record_id=item.id,
        action="update",
        changed_by=current.id,
        old_values=old_values,
        new_values=item.model_dump(),
    )
    await session.commit()
    await session.refresh(item)

    return item


@router.delete("/{item_id}", status_code=204, dependencies=[Depends(require_min_tier(2))])
async def delete_item(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    old_values = item.model_dump()
    await session.delete(item)

    await log_audit(
        session,
        table_name="item",
        record_id=item_id,
        action="delete",
        changed_by=current.id,
        old_values=old_values,
    )
    await session.commit()
