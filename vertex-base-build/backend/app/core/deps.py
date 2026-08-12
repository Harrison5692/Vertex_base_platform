from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.account import Account

bearer_scheme = HTTPBearer()


async def get_current_account(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> Account:
    email = decode_access_token(credentials.credentials)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await session.exec(select(Account).where(Account.email == email))
    account = result.first()
    if not account or not account.is_active:
        raise HTTPException(status_code=401, detail="Account not found or inactive")
    return account


def require_min_tier(min_tier: int):
    """
    Dependency factory — require_min_tier(2) means "tier 2 or higher
    only". Open-ended on purpose: a deployment with 5 tiers uses this
    exactly the same way a 2-tier one does, no code change needed.
    """

    async def _check(account: Account = Depends(get_current_account)) -> Account:
        if account.tier < min_tier:
            raise HTTPException(
                status_code=403, detail=f"Requires tier {min_tier} or higher"
            )
        return account

    return _check
