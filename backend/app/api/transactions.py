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

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import get_current_account, require_min_tier
from app.db.session import get_session
from app.models.account import Account
from app.models.transaction import Transaction, TransactionCreate, TransactionRead
from app.models.transaction_line import (
    TransactionLine,
    TransactionLineCreate,
    TransactionLineRead,
)
from pydantic import BaseModel

router = APIRouter(
    prefix="/transactions", tags=["transactions"], dependencies=[Depends(get_current_account)]
)


class TransactionWithLines(TransactionRead):
    lines: list[TransactionLineRead] = []


class TransactionCreateRequest(TransactionCreate):
    lines: list[TransactionLineCreate]
    tax_amount: float | None = None


@router.get(
    "/", response_model=list[TransactionRead], dependencies=[Depends(require_min_tier(2))]
)
async def list_transactions(session: AsyncSession = Depends(get_session)):
    """Staff and above only — every transaction, across every account."""
    result = await session.exec(select(Transaction).order_by(Transaction.created_at.desc()))
    return result.all()


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
    if tx_in.account_id is not None:
        account = await session.get(Account, tx_in.account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

    if not tx_in.lines:
        raise HTTPException(status_code=422, detail="A transaction needs at least one line item")

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
    await session.commit()
    await session.refresh(transaction)

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
    await session.commit()
    for line in lines:
        await session.refresh(line)

    return TransactionWithLines(**transaction.model_dump(), lines=lines)
