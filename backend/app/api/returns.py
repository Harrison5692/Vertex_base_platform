"""
Staff-only endpoints for logging a physical return and later deciding
what happens to each returned item. See models/return_item.py for the
full design rationale.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit import log_audit
from app.core.deps import get_current_account, require_min_tier
from app.db.session import get_session
from app.models.account import Account
from app.models.item import Item
from app.models.return_item import (
    ResolveReturnLineRequest,
    ReturnLine,
    ReturnLineRead,
    ReturnLineStatus,
    ReturnRequest,
    ReturnRequestCreate,
    ReturnRequestRead,
)
from app.models.transaction import Transaction, TransactionType

router = APIRouter(
    prefix="/returns", tags=["returns"], dependencies=[Depends(require_min_tier(2))]
)


@router.post("/", response_model=ReturnRequestRead, status_code=201)
async def create_return(
    body: ReturnRequestCreate,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """Logs which physical items are coming back for a refund that's
    already been issued. Every line starts pending_inspection —
    resolving it (restock / restock at a discount / discard) is a
    separate step via PATCH below, since staff often need to actually
    look at the item before deciding."""
    refund_tx = await session.get(Transaction, body.refund_transaction_id)
    if not refund_tx:
        raise HTTPException(status_code=404, detail="Refund transaction not found")
    if refund_tx.type != TransactionType.refunded:
        raise HTTPException(
            status_code=422,
            detail="refund_transaction_id must point to a refund transaction",
        )

    if not body.lines:
        raise HTTPException(status_code=422, detail="A return needs at least one line item")

    item_ids = {line.item_id for line in body.lines}
    result = await session.exec(select(Item.id).where(Item.id.in_(item_ids)))
    missing = item_ids - set(result.all())
    if missing:
        raise HTTPException(status_code=404, detail=f"Item id(s) not found: {sorted(missing)}")

    return_request = ReturnRequest(
        refund_transaction_id=body.refund_transaction_id,
        notes=body.notes,
        created_by=current.id,
    )
    session.add(return_request)
    await session.flush()

    lines = []
    for line_in in body.lines:
        line = ReturnLine(
            return_request_id=return_request.id,
            item_id=line_in.item_id,
            quantity=line_in.quantity,
        )
        session.add(line)
        lines.append(line)
    await session.flush()

    await log_audit(
        session,
        table_name="return_request",
        record_id=return_request.id,
        action="create",
        changed_by=current.id,
        new_values={**return_request.model_dump(), "lines": [ln.model_dump() for ln in lines]},
    )
    await session.commit()
    await session.refresh(return_request)
    for line in lines:
        await session.refresh(line)

    return ReturnRequestRead(**return_request.model_dump(), lines=lines)


@router.get("/", response_model=list[ReturnRequestRead])
async def list_returns(
    pending_only: bool = False,
    session: AsyncSession = Depends(get_session),
):
    """pending_only=true returns only requests that have at least one
    unresolved line — the "needs a decision" queue. Otherwise every
    return request, most recent first, resolved or not."""
    result = await session.exec(select(ReturnRequest).order_by(ReturnRequest.created_at.desc()))
    requests = result.all()

    lines_result = await session.exec(
        select(ReturnLine).where(
            ReturnLine.return_request_id.in_([r.id for r in requests] or [-1])
        )
    )
    lines_by_request: dict[int, list[ReturnLine]] = {}
    for line in lines_result.all():
        lines_by_request.setdefault(line.return_request_id, []).append(line)

    reads = [
        ReturnRequestRead(**r.model_dump(), lines=lines_by_request.get(r.id, []))
        for r in requests
    ]
    if pending_only:
        reads = [
            r
            for r in reads
            if any(ln.status == ReturnLineStatus.pending_inspection for ln in r.lines)
        ]
    return reads


@router.patch("/{return_id}/lines/{line_id}", response_model=ReturnLineRead)
async def resolve_return_line(
    return_id: int,
    line_id: int,
    body: ResolveReturnLineRequest,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """Decides what happens to one returned item. Terminal once
    resolved — a line can't be re-resolved to a different outcome
    after the fact; log a fresh return if that's genuinely needed."""
    return_request = await session.get(ReturnRequest, return_id)
    if not return_request:
        raise HTTPException(status_code=404, detail="Return not found")

    line = await session.get(ReturnLine, line_id)
    if not line or line.return_request_id != return_id:
        raise HTTPException(status_code=404, detail="Return line not found")
    if line.status != ReturnLineStatus.pending_inspection:
        raise HTTPException(
            status_code=409, detail=f"This line is already {line.status.value} — that's final"
        )
    if body.status == ReturnLineStatus.pending_inspection:
        raise HTTPException(status_code=422, detail="Choose an actual outcome, not pending")
    if body.status == ReturnLineStatus.restocked_discounted and body.discount_price is None:
        raise HTTPException(
            status_code=422, detail="discount_price is required for restocked_discounted"
        )

    # Lock the original item row for the duration of the stock change,
    # same reasoning as checkout — two staff resolving different
    # return lines for the same item shouldn't race on its stock count.
    result = await session.exec(select(Item).where(Item.id == line.item_id).with_for_update())
    item = result.first()
    if not item:
        raise HTTPException(status_code=404, detail="The original item no longer exists")

    if body.status == ReturnLineStatus.restocked:
        item.stock_quantity = (item.stock_quantity or 0) + line.quantity
        session.add(item)

    elif body.status == ReturnLineStatus.restocked_discounted:
        # Reuse an existing clearance listing at the same discount
        # price if one's already open, rather than spawning a new Item
        # row every single time a return gets discounted-restocked.
        existing_result = await session.exec(
            select(Item)
            .where(
                Item.parent_item_id == item.id,
                Item.price == body.discount_price,
                Item.is_active == True,  # noqa: E712
            )
            .with_for_update()
        )
        clearance_item = existing_result.first()
        if clearance_item:
            clearance_item.stock_quantity = (clearance_item.stock_quantity or 0) + line.quantity
            session.add(clearance_item)
        else:
            clearance_item = Item(
                name=f"{item.name} (Clearance)",
                description=item.description,
                category=item.category,
                image_url=item.image_url,
                price=body.discount_price,
                stock_quantity=line.quantity,
                parent_item_id=item.id,
                is_active=True,
            )
            session.add(clearance_item)
            await session.flush()  # assigns clearance_item.id
        line.discount_item_id = clearance_item.id

    # discarded: no stock change anywhere — the item just leaves
    # inventory entirely, which is the point of that outcome.

    old_status = line.status
    line.status = body.status
    line.resolved_at = datetime.utcnow()
    line.resolved_by = current.id
    session.add(line)

    await log_audit(
        session,
        table_name="return_line",
        record_id=line.id,
        action="update",
        changed_by=current.id,
        old_values={"status": old_status},
        new_values={"status": body.status, "discount_item_id": line.discount_item_id},
    )
    await session.commit()
    await session.refresh(line)

    return line
