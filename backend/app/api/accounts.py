"""
General account management. Tier gates access throughout:
- Tier 1 (e.g. clients) can view/update only their own record.
- Tier 2+ (staff) can view/manage everyone.
This is the concrete demonstration of the tiered-access pattern —
copy it for any other resource that needs the same self-vs-staff split.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit import log_audit
from app.core.deps import get_current_account, require_min_tier
from app.db.session import get_session
from app.models.account import Account, AccountRead, AccountUpdate
from app.models.deleted_account import DeletedAccount

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/", response_model=list[AccountRead], dependencies=[Depends(require_min_tier(2))])
async def list_accounts(session: AsyncSession = Depends(get_session)):
    """Staff and above only — full account list."""
    result = await session.exec(select(Account).where(Account.is_active == True))  # noqa: E712
    return result.all()


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """Self, or staff and above — tier-1 accounts can only fetch their own record."""
    if current.tier < 2 and current.id != account_id:
        raise HTTPException(status_code=403, detail="Can only view your own account")

    account = await session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.patch("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: int,
    account_in: AccountUpdate,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    if current.tier < 2 and current.id != account_id:
        raise HTTPException(status_code=403, detail="Can only update your own account")
    # Only staff+ may change someone's tier — a client can't self-promote.
    if account_in.tier is not None and current.tier < 2:
        raise HTTPException(status_code=403, detail="Only staff may change account tier")

    account = await session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    old_values = account.model_dump(exclude={"hashed_password"})
    for field, value in account_in.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    session.add(account)

    await log_audit(
        session,
        table_name="account",
        record_id=account.id,
        action="update",
        changed_by=current.id,
        old_values=old_values,
        new_values=account.model_dump(exclude={"hashed_password"}),
    )
    await session.commit()
    await session.refresh(account)

    return account


@router.delete(
    "/{account_id}", status_code=204, dependencies=[Depends(require_min_tier(2))]
)
async def deactivate_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """Soft delete — sets is_active False, never removes the row.
    Also logs an archive entry so the deactivation is easy to find
    and reverse later. Staff and above only."""
    account = await session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.is_active = False
    session.add(account)

    archive_entry = DeletedAccount(
        account_id=account.id,
        tier_at_deletion=account.tier,
        name=account.name,
        email=account.email,
        deleted_by=current.id,
    )
    session.add(archive_entry)

    await log_audit(
        session,
        table_name="account",
        record_id=account.id,
        action="delete",
        changed_by=current.id,
        old_values={"is_active": True},
        new_values={"is_active": False},
    )
    await session.commit()


@router.post("/{account_id}/reinstate", response_model=AccountRead)
async def reinstate_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(require_min_tier(2)),
):
    """Reverses a deactivation — staff and above only."""
    account = await session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.is_active = True
    session.add(account)

    result = await session.exec(
        select(DeletedAccount)
        .where(
            DeletedAccount.account_id == account_id,
            DeletedAccount.restored_at.is_(None),
        )
        .order_by(DeletedAccount.deleted_at.desc())
    )
    archive_entry = result.first()
    if archive_entry:
        from datetime import datetime

        archive_entry.restored_at = datetime.utcnow()
        session.add(archive_entry)

    await log_audit(
        session,
        table_name="account",
        record_id=account.id,
        action="update",
        changed_by=current.id,
        old_values={"is_active": False},
        new_values={"is_active": True},
    )
    await session.commit()
    await session.refresh(account)

    return account
