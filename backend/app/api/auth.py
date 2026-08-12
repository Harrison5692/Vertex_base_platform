from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import get_current_account
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_session
from app.models.account import Account, AccountCreate, AccountRead

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(SQLModel):
    email: str
    password: str


@router.post("/register", response_model=AccountRead, status_code=201)
async def register(account_in: AccountCreate, session: AsyncSession = Depends(get_session)):
    """
    Public self-registration — as shipped, this creates whatever tier
    is passed in, which is fine for a demo/template but almost
    certainly wrong for a real deployment: in production, restrict
    who can create tier 2+ (staff) accounts — e.g. only an existing
    tier-2+ account should be able to promote someone, not the open
    registration form.
    """
    existing = await session.exec(select(Account).where(Account.email == account_in.email))
    if existing.first():
        raise HTTPException(status_code=409, detail="Email already registered")

    account = Account(
        email=account_in.email,
        name=account_in.name,
        phone=account_in.phone,
        tier=account_in.tier,
        is_active=account_in.is_active,
        hashed_password=hash_password(account_in.password) if account_in.password else None,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


@router.post("/login")
async def login(credentials: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Account).where(Account.email == credentials.email))
    account = result.first()
    if not account or not account.can_login:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not verify_password(credentials.password, account.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not account.is_active:
        raise HTTPException(status_code=401, detail="Account is inactive")

    token = create_access_token(subject=account.email)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=AccountRead)
async def read_current_account(current_account: Account = Depends(get_current_account)):
    return current_account
