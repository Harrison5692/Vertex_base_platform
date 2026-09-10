from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.account import Account

bearer_scheme = HTTPBearer()
# auto_error=False: unlike bearer_scheme above, this doesn't 401 on a
# missing Authorization header — it lets the endpoint see "no token"
# and decide for itself (e.g. guest checkout). A header that IS
# present but invalid/expired still raises 401 below, same as the
# required version — silently treating a broken session as "guest"
# would be a confusing failure mode for someone who thought they
# were logged in.
bearer_scheme_optional = HTTPBearer(auto_error=False)


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


async def get_current_account_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme_optional),
    session: AsyncSession = Depends(get_session),
) -> Account | None:
    """Same checks as get_current_account, but returns None instead of
    401 when no Authorization header was sent at all. Use this on an
    endpoint that legitimately serves both logged-in and anonymous
    requests (currently just guest checkout) — everything else should
    keep using the required get_current_account/require_min_tier."""
    if credentials is None:
        return None
    return await get_current_account(credentials, session)


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
