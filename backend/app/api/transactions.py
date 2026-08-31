"""
History log — every meaningful action, timestamped and tied to the
account it involved (if any — see guest_label on the model) and the
account that performed it. Read-heavy by design: this is the
audit-friendly record a business (or a regulator) would want to
review, so there's deliberately no update/delete endpoint — history
doesn't get edited after the fact, only appended to (refund/void are
new Transaction rows, not edits of the original).

A transaction is created with its line items in one call — the
client sends item_id/quantity/unit_price pairs, the server computes
subtotal/total and writes both the Transaction header and its
TransactionLine rows atomically.

Access follows the same tier pattern as accounts.py: a tier-1 account
sees only their own transactions, tier-2+ (staff) can see anyone's.
"""

from datetime import datetime
import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit import log_audit
from app.core.deps import get_current_account, require_min_tier
from app.core.email import get_email_provider
from app.db.session import get_session
from app.models.account import Account
from app.models.item import Item
from app.models.transaction import Transaction, TransactionCreate, TransactionRead, TransactionType
from app.models.transaction_line import (
    TransactionLine,
    TransactionLineCreate,
    TransactionLineRead,
)

router = APIRouter(
    prefix="/transactions", tags=["transactions"], dependencies=[Depends(get_current_account)]
)


class TransactionWithLines(TransactionRead):
    lines: list[TransactionLineRead] = []


class TransactionCreateRequest(TransactionCreate):
    lines: list[TransactionLineCreate]
    tax_amount: float | None = PydanticField(default=None, ge=0)


class RefundRequest(BaseModel):
    amount: float | None = PydanticField(default=None, gt=0)  # None = full refund of the original total
    notes: str | None = None


@router.get(
    "/", response_model=list[TransactionRead], dependencies=[Depends(require_min_tier(2))]
)
async def list_transactions(session: AsyncSession = Depends(get_session)):
    """Staff and above only — every transaction, across every account."""
    result = await session.exec(select(Transaction).order_by(Transaction.created_at.desc()))
    return result.all()


@router.get("/export", dependencies=[Depends(require_min_tier(2))])
async def export_transactions(
    session: AsyncSession = Depends(get_session),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """Staff and above only. CSV export of transaction history —
    every business wants a copy of its own sales data outside the
    system (accounting, taxes, a spreadsheet). Deliberately placed
    BEFORE /{transaction_id} below: a static path must be registered
    ahead of a dynamic one sharing the same prefix, or FastAPI tries
    to parse "export" as a transaction id and 422s before ever
    reaching this route."""
    query = select(Transaction).order_by(Transaction.created_at.asc())
    if start_date:
        query = query.where(Transaction.created_at >= start_date)
    if end_date:
        query = query.where(Transaction.created_at <= end_date)
    result = await session.exec(query)
    transactions = result.all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id", "created_at", "type", "account_id", "guest_label", "payment_method",
            "payment_reference", "subtotal", "tax_amount", "total",
            "deposit_amount", "balance_due", "related_transaction_id", "created_by", "notes",
        ]
    )
    for tx in transactions:
        writer.writerow(
            [
                tx.id, tx.created_at.isoformat(), tx.type, tx.account_id, tx.guest_label,
                tx.payment_method, tx.payment_reference, tx.subtotal, tx.tax_amount, tx.total,
                tx.deposit_amount, tx.balance_due, tx.related_transaction_id, tx.created_by,
                tx.notes,
            ]
        )
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


@router.get("/account/{account_id}", response_model=list[TransactionRead])
async def get_account_history(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """A single account's full history — self, or staff and above."""
    if current.tier < 2 and current.id != account_id:
        raise HTTPException(status_code=403, detail="Can only view your own history")

    account = await session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    result = await session.exec(
        select(Transaction)
        .where(Transaction.account_id == account_id)
        .order_by(Transaction.created_at.desc())
    )
    return result.all()


@router.get("/{transaction_id}", response_model=TransactionWithLines)
async def get_transaction(
    transaction_id: int,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """A single transaction with its line items — self, or staff and above."""
    transaction = await session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if current.tier < 2 and current.id != transaction.account_id:
        raise HTTPException(status_code=403, detail="Can only view your own transactions")

    result = await session.exec(
        select(TransactionLine).where(TransactionLine.transaction_id == transaction_id)
    )
    lines = result.all()
    return TransactionWithLines(**transaction.model_dump(), lines=lines)


@router.post("/", response_model=TransactionWithLines, status_code=201)
async def create_transaction(
    tx_in: TransactionCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_account: Account = Depends(get_current_account),
):
    """account_id is optional — a guest/walk-in sale passes null and
    relies on guest_label instead. Requires at least one line item;
    subtotal/total are computed server-side from the lines, never
    trusted from the client."""
    account = None
    if tx_in.account_id is not None:
        account = await session.get(Account, tx_in.account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

    if not tx_in.lines:
        raise HTTPException(status_code=422, detail="A transaction needs at least one line item")

    # Validate every referenced item exists BEFORE creating anything —
    # letting a bad item_id reach the database insert means a raw FK
    # violation (500) instead of a clean, actionable error.
    item_ids = {line.item_id for line in tx_in.lines}
    result = await session.exec(select(Item.id).where(Item.id.in_(item_ids)))
    found_ids = set(result.all())
    missing_ids = item_ids - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Item id(s) not found: {sorted(missing_ids)}",
        )

    subtotal = sum(line.quantity * line.unit_price for line in tx_in.lines)
    tax_amount = tx_in.tax_amount or 0.0
    total = subtotal + tax_amount

    tx_data = tx_in.model_dump(exclude={"lines", "tax_amount"})
    transaction = Transaction.model_validate(
        tx_data,
        update={
            "created_by": current_account.id,
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total": total,
        },
    )
    session.add(transaction)
    await session.flush()  # assigns transaction.id without committing/expiring attributes

    lines = []
    for line_in in tx_in.lines:
        line = TransactionLine(
            transaction_id=transaction.id,
            item_id=line_in.item_id,
            quantity=line_in.quantity,
            unit_price=line_in.unit_price,
            line_total=line_in.quantity * line_in.unit_price,
        )
        session.add(line)
        lines.append(line)
    await session.flush()  # assigns each line.id, still no commit/expire

    await log_audit(
        session,
        table_name="transaction",
        record_id=transaction.id,
        action="create",
        changed_by=current_account.id,
        new_values={**transaction.model_dump(), "lines": [l.model_dump() for l in lines]},
    )
    await session.commit()
    await session.refresh(transaction)
    for line in lines:
        await session.refresh(line)

    # Order confirmation — only when there's a real account to email;
    # a guest/walk-in sale (guest_label, no account_id) has no address
    # to send to.
    if account is not None:
        provider = get_email_provider()
        await provider.send(
            to=account.email,
            subject="Order confirmation",
            body=f"Thanks for your order — total ${transaction.total:.2f}, transaction #{transaction.id}.",
        )

    return TransactionWithLines(**transaction.model_dump(), lines=lines)


@router.post("/{transaction_id}/refund", response_model=TransactionWithLines, status_code=201)
async def refund_transaction(
    transaction_id: int,
    body: RefundRequest,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(require_min_tier(2)),
):
    """Staff and above only. Creates a NEW transaction of type
    'refunded' linked back to the original via related_transaction_id
    — the original row is never edited, per the append-only history
    rule. Defaults to a full refund of the original's total; pass
    `amount` for a partial refund. Line items aren't itemized on the
    refund by default (a partial refund isn't necessarily tied to
    specific items) — that's a vertical-specific extension if a
    deployment needs it."""
    original = await session.get(Transaction, transaction_id)
    if not original:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if original.type in (TransactionType.refunded, TransactionType.voided):
        raise HTTPException(status_code=409, detail="Cannot refund a refund/void transaction itself")

    # The original transaction's own `type` never changes (append-only
    # history) — so "already refunded" has to be checked by looking for
    # an EXISTING refund row that points back at this one, not by
    # inspecting original.type.
    existing_refund = await session.exec(
        select(Transaction).where(
            Transaction.related_transaction_id == transaction_id,
            Transaction.type == TransactionType.refunded,
        )
    )
    if existing_refund.first():
        raise HTTPException(status_code=409, detail="Transaction has already been refunded")

    refund_amount = body.amount if body.amount is not None else (original.total or 0.0)
    if refund_amount <= 0 or refund_amount > (original.total or 0.0):
        raise HTTPException(status_code=422, detail="Refund amount must be > 0 and <= original total")

    refund = Transaction(
        account_id=original.account_id,
        guest_label=original.guest_label,
        type=TransactionType.refunded,
        payment_method=original.payment_method,
        notes=body.notes,
        related_transaction_id=original.id,
        subtotal=-refund_amount,
        tax_amount=0.0,
        total=-refund_amount,
        created_by=current.id,
    )
    session.add(refund)
    await session.flush()  # assigns refund.id without committing/expiring attributes

    await log_audit(
        session,
        table_name="transaction",
        record_id=refund.id,
        action="create",
        changed_by=current.id,
        new_values={**refund.model_dump(), "refunds_transaction_id": original.id},
    )
    await session.commit()
    await session.refresh(refund)

    return TransactionWithLines(**refund.model_dump(), lines=[])
