"""
Single account table for anyone the system knows about — client,
staff, or higher-level staff — distinguished by a numeric `tier`
rather than a fixed enum. This is the deliberate design: a client
years from now might need five tiers, another might only ever need
two. A tier is just an integer; no schema change required to add one.

Default convention (a starting point, not a hard rule — each
deployment defines what its own tiers mean):
  1 = client / customer / patient / organization (the base template default)
  2 = staff
  3+ = higher-level staff / management / admin

hashed_password is nullable on purpose: a tier-1 record can exist
purely as a record (no portal login, just history/transactions tied
to them) OR as a real login-capable account, depending on what a
given deployment needs. can_login reflects which case it is.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class AccountBase(SQLModel):
    email: str = Field(unique=True, index=True, max_length=255)
    name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    tier: int = Field(default=1, index=True)
    is_active: bool = Field(default=True, index=True)


class Account(AccountBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def can_login(self) -> bool:
        return self.hashed_password is not None


class AccountCreate(AccountBase):
    password: str | None = None  # omit for a record-only account with no login


class AccountRead(AccountBase):
    id: int
    created_at: datetime


class AccountUpdate(SQLModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    tier: int | None = None
    is_active: bool | None = None
