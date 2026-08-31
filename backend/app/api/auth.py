from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import EmailStr
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit import log_audit
from app.core.deps import get_current_account
from app.core.email import get_email_provider
from app.core.rate_limit import rate_limit
from app.core.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.db.session import get_session
from app.models.account import Account, AccountCreate, AccountRead

router = APIRouter(prefix="/auth", tags=["auth"])

RESET_TOKEN_EXPIRE_MINUTES = 30


class LoginRequest(SQLModel):
    email: EmailStr
    password: str


class PasswordResetRequest(SQLModel):
    email: EmailStr


class PasswordResetConfirm(SQLModel):
    token: str
    new_password: str


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
    await session.flush()  # assigns account.id without committing/expiring attributes

    await log_audit(
        session,
        table_name="account",
        record_id=account.id,
        action="create",
        changed_by=account.id,  # self-registration — the account created itself
        new_values=account.model_dump(exclude={"hashed_password"}),
    )
    await session.commit()
    await session.refresh(account)

    return account


@router.post("/login", dependencies=[Depends(rate_limit("login", max_attempts=5, window_seconds=300))])
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


@router.post(
    "/request-password-reset",
    dependencies=[Depends(rate_limit("password-reset", max_attempts=3, window_seconds=900))],
)
async def request_password_reset(
    body: PasswordResetRequest, session: AsyncSession = Depends(get_session)
):
    """
    Issues a reset token if the email matches a login-capable account.
    Always returns the same generic message regardless of whether the
    email exists — this prevents the endpoint being used to enumerate
    which emails are registered.

    NOTE: this base build has no email-sending integration wired up.
    The raw token is returned directly in the response so the flow is
    testable end-to-end without one — a real deployment MUST remove
    the token from the response body and email it instead, or anyone
    who knows an account's email can reset that account's password.
    """
    result = await session.exec(select(Account).where(Account.email == body.email))
    account = result.first()

    generic_response = {"message": "If that email exists, a reset link has been issued."}

    if not account or not account.can_login:
        return generic_response

    raw_token = generate_reset_token()
    account.reset_token_hash = hash_reset_token(raw_token)
    account.reset_token_expires = datetime.utcnow() + timedelta(
        minutes=RESET_TOKEN_EXPIRE_MINUTES
    )
    session.add(account)
    await session.commit()

    provider = get_email_provider()
    await provider.send(
        to=account.email,
        subject="Reset your password",
        body=f"Your password reset code is: {raw_token}\nExpires in {RESET_TOKEN_EXPIRE_MINUTES} minutes.",
    )

    # DEV-ONLY: still returned directly so the flow is testable without a
    # real provider wired in. Remove this field once a real EmailProvider
    # is actually delivering the message above — see CUSTOMIZING.md.
    generic_response["dev_reset_token"] = raw_token
    return generic_response


@router.post("/reset-password", response_model=AccountRead)
async def reset_password(
    body: PasswordResetConfirm, session: AsyncSession = Depends(get_session)
):
    token_hash = hash_reset_token(body.token)
    result = await session.exec(
        select(Account).where(Account.reset_token_hash == token_hash)
    )
    account = result.first()

    if (
        not account
        or account.reset_token_expires is None
        or account.reset_token_expires < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    account.hashed_password = hash_password(body.new_password)
    account.reset_token_hash = None
    account.reset_token_expires = None
    session.add(account)

    await log_audit(
        session,
        table_name="account",
        record_id=account.id,
        action="update",
        changed_by=account.id,
        new_values={"password_reset": True},
    )
    await session.commit()
    await session.refresh(account)

    return account
