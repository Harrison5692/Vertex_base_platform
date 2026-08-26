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
from app.core.deps import get_current_account
from app.db.session import get_session
from app.models.account import Account
from app.models.item import Item, ItemCreate, ItemRead, ItemUpdate

router = APIRouter(
    prefix="/items", tags=["items"], dependencies=[Depends(get_current_account)]
)


@router.get("/", response_model=list[ItemRead])
async def list_items(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Item))
    return result.all()


@router.post("/", response_model=ItemRead, status_code=201)
async def create_item(
    item_in: ItemCreate,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    item = Item.model_validate(item_in)
    session.add(item)
    await session.flush()  # assigns item.id without committing/expiring attributes

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


@router.patch("/{item_id}", response_model=ItemRead)
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
    for field, value in item_in.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    session.add(item)

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


@router.delete("/{item_id}", status_code=204)
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
