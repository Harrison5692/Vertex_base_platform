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
from app.core.stock import maybe_notify_low_stock
from app.db.session import get_session
from app.models.account import Account
from app.models.item import Item, ItemCreate, ItemRead, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])
# No router-level auth dependency — GET routes are intentionally public
# (browsing a catalog shouldn't require an account, same as any real
# storefront). POST/PATCH/DELETE below each carry their own
# require_min_tier(2), which pulls in get_current_account internally —
# so mutations are still fully auth-gated, just not via a blanket
# router-level requirement that would also lock out browsing.


@router.get("/", response_model=list[ItemRead])
async def list_items(
    session: AsyncSession = Depends(get_session),
    q: str | None = None,
    category: str | None = None,
):
    """q does a case-insensitive substring match on name. Both filters
    are optional and combine with AND when both are given. Deliberately
    simple (no full-text search engine) — this is meant to work for a
    catalog of dozens-to-low-hundreds of items, not power a large-scale
    storefront search; that would be a real addition, not a base one."""
    query = select(Item)
    if q:
        query = query.where(Item.name.ilike(f"%{q}%"))
    if category:
        query = query.where(Item.category == category)
    result = await session.exec(query)
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

    await maybe_notify_low_stock(session, item, previous_stock=None, current_account_id=current.id)

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

    await maybe_notify_low_stock(
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
