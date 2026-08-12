"""
History log — every meaningful action, timestamped and tied to the
account it involved and the account that performed it. Read-heavy
by design: this is the audit-friendly record a business (or a
regulator) would want to review, so there's deliberately no
update/delete endpoint — history doesn't get edited after the fact.

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

router = APIRouter(
    prefix="/transactions", tags=["transactions"], dependencies=[Depends(get_current_account)]
)


@router.get("/", response_model=list[TransactionRead], dependencies=[Depends(require_min_tier(2))])
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


@router.post("/", response_model=TransactionRead, status_code=201)
async def create_transaction(
    tx_in: TransactionCreate,
    session: AsyncSession = Depends(get_session),
    current_account: Account = Depends(get_current_account),
):
    account = await session.get(Account, tx_in.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    transaction = Transaction.model_validate(tx_in, update={"created_by": current_account.id})
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction
