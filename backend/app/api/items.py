"""
Example CRUD router — replace `Item` with your real entities.

Every client build starts by copying this file's pattern for each
of their actual domain objects (patients, orders, devices, whatever
the business runs on). Routes are auth-protected — copy that pattern
too for any real resource. Also copy the audit-log pattern: every
create/update/delete writes an AuditLog row alongside the change.
"""

from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit import log_audit
from app.core.deps import get_current_account, require_min_tier
from app.core.stock import maybe_notify_low_stock
from app.db.session import get_session
from app.models.account import Account
from app.models.item import Item, ItemCreate, ItemRead, ItemUpdate
from app.models.item_image import ItemImage, ItemImageCreate

router = APIRouter(prefix="/items", tags=["items"])
# No router-level auth dependency — GET routes are intentionally public
# (browsing a catalog shouldn't require an account, same as any real
# storefront). POST/PATCH/DELETE below each carry their own
# require_min_tier(2), which pulls in get_current_account internally —
# so mutations are still fully auth-gated, just not via a blanket
# router-level requirement that would also lock out browsing.


class ItemSort(str, Enum):
    newest = "newest"
    price_asc = "price_asc"
    price_desc = "price_desc"


@router.get("/", response_model=list[ItemRead])
async def list_items(
    session: AsyncSession = Depends(get_session),
    q: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    sort: ItemSort | None = None,
    standalone_only: bool = False,
):
    """q does a case-insensitive substring match on name. Filters
    combine with AND when several are given. Deliberately simple (no
    full-text search engine) — this is meant to work for a catalog of
    dozens-to-low-hundreds of items, not power a large-scale
    storefront search; that would be a real addition, not a base one.

    standalone_only=true excludes variant rows (items with
    variant_parent_id set) — the storefront passes this so a product
    with 5 size/color variants shows as ONE card, not five. The staff
    admin table leaves it false, since managing each variant's own
    price/stock individually requires seeing them."""
    query = select(Item)
    if q:
        query = query.where(Item.name.ilike(f"%{q}%"))
    if category:
        query = query.where(Item.category == category)
    if min_price is not None:
        query = query.where(Item.price >= min_price)
    if max_price is not None:
        query = query.where(Item.price <= max_price)
    if standalone_only:
        query = query.where(Item.variant_parent_id.is_(None))

    if sort == ItemSort.price_asc:
        query = query.order_by(Item.price.asc().nulls_last())
    elif sort == ItemSort.price_desc:
        query = query.order_by(Item.price.desc().nulls_last())
    elif sort == ItemSort.newest:
        query = query.order_by(Item.created_at.desc())

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


@router.get("/{item_id}/variants", response_model=list[ItemRead])
async def list_item_variants(item_id: int, session: AsyncSession = Depends(get_session)):
    """Public. Every Item row with variant_parent_id == item_id — e.g.
    each size/color combination of a base product. Empty list for an
    item with no variants, which is most items; this is opt-in per
    product, not a forced concept."""
    result = await session.exec(
        select(Item).where(Item.variant_parent_id == item_id).order_by(Item.id.asc())
    )
    return result.all()


@router.get("/{item_id}/images")
async def list_item_images(item_id: int, session: AsyncSession = Depends(get_session)):
    """Public. Gallery images beyond the item's primary image_url —
    see models/item_image.py for why these are kept separate."""
    result = await session.exec(
        select(ItemImage).where(ItemImage.item_id == item_id).order_by(ItemImage.sort_order.asc())
    )
    return [row.url for row in result.all()]


@router.post(
    "/{item_id}/images", status_code=201, dependencies=[Depends(require_min_tier(2))]
)
async def add_item_image(
    item_id: int,
    body: ItemImageCreate,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    existing_result = await session.exec(
        select(ItemImage).where(ItemImage.item_id == item_id)
    )
    next_order = len(existing_result.all())

    image = ItemImage(item_id=item_id, url=body.url, sort_order=next_order)
    session.add(image)
    await session.flush()

    await log_audit(
        session,
        table_name="item_image",
        record_id=image.id,
        action="create",
        changed_by=current.id,
        new_values=image.model_dump(),
    )
    await session.commit()
    await session.refresh(image)
    return {"id": image.id, "url": image.url, "sort_order": image.sort_order}


@router.delete(
    "/{item_id}/images/{image_id}", status_code=204, dependencies=[Depends(require_min_tier(2))]
)
async def delete_item_image(
    item_id: int,
    image_id: int,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    image = await session.get(ItemImage, image_id)
    if not image or image.item_id != item_id:
        raise HTTPException(status_code=404, detail="Image not found")
    old_values = image.model_dump()
    await session.delete(image)

    await log_audit(
        session,
        table_name="item_image",
        record_id=image_id,
        action="delete",
        changed_by=current.id,
        old_values=old_values,
    )
    await session.commit()


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
