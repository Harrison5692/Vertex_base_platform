"""
Cart for logged-in accounts. See models/cart_item.py for why this
exists and why it's whole-replace rather than per-line endpoints.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import get_current_account
from app.db.session import get_session
from app.models.account import Account
from app.models.cart_item import CartItem, CartLineOut, CartReplaceRequest
from app.models.item import Item

router = APIRouter(prefix="/cart", tags=["cart"])


async def _cart_with_item_details(session: AsyncSession, account_id: int) -> list[CartLineOut]:
    result = await session.exec(select(CartItem).where(CartItem.account_id == account_id))
    cart_rows = result.all()
    if not cart_rows:
        return []

    item_ids = {row.item_id for row in cart_rows}
    items_result = await session.exec(select(Item).where(Item.id.in_(item_ids)))
    items_by_id = {item.id: item for item in items_result.all()}

    # A cart row for an item that's since been deleted is silently
    # dropped from the response (nothing to show) rather than erroring
    # — the row itself is left alone; it'll just keep being skipped
    # until the account's cart is next replaced wholesale.
    out = []
    for row in cart_rows:
        item = items_by_id.get(row.item_id)
        if not item:
            continue
        out.append(
            CartLineOut(
                item_id=row.item_id,
                quantity=row.quantity,
                name=item.name,
                unit_price=item.price,
                image_url=item.image_url,
            )
        )
    return out


@router.get("/", response_model=list[CartLineOut])
async def get_cart(
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    return await _cart_with_item_details(session, current.id)


@router.put("/", response_model=list[CartLineOut])
async def replace_cart(
    body: CartReplaceRequest,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """Replaces the account's entire cart with exactly what's sent —
    an empty `lines` list clears it. This is how the frontend both
    updates a quantity and removes a line (just omit it), and how a
    guest's localStorage cart gets merged in at login (the frontend
    fetches the current server cart, combines it with whatever was
    local, and PUTs the merged result back)."""
    existing_result = await session.exec(
        select(CartItem).where(CartItem.account_id == current.id)
    )
    for row in existing_result.all():
        await session.delete(row)
    await session.flush()

    now = datetime.utcnow()
    for line in body.lines:
        session.add(
            CartItem(
                account_id=current.id,
                item_id=line.item_id,
                quantity=line.quantity,
                updated_at=now,
            )
        )
    await session.commit()

    return await _cart_with_item_details(session, current.id)
