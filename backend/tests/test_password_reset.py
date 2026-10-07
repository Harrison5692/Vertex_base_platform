"""Password reset request — must not crash, and must never leak the
reset code outside development."""

import pytest

from app.core.config import settings
from app.core.security import hash_password
from app.db import session as db_session
from app.models.account import Account
from sqlmodel.ext.asyncio.session import AsyncSession

pytestmark = pytest.mark.asyncio


async def _account(email):
    async with AsyncSession(db_session.engine) as s:
        s.add(Account(email=email, hashed_password=hash_password("pw-12345678")))
        await s.commit()


async def test_reset_request_works_and_returns_dev_token_in_development(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    await _account("dev@example.com")
    r = await client.post("/auth/request-password-reset", json={"email": "dev@example.com"})
    assert r.status_code == 200, r.text
    assert "dev_reset_token" in r.json()


async def test_reset_request_never_leaks_token_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    await _account("prod@example.com")
    r = await client.post("/auth/request-password-reset", json={"email": "prod@example.com"})
    assert r.status_code == 200, r.text
    assert "dev_reset_token" not in r.json()
