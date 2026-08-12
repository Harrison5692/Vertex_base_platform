"""
The business's customers — not people who log into this system,
just records the business maintains. Soft-delete via is_active,
never hard-deleted, so history/transactions never orphan.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class ClientBase(SQLModel):
    name: str = Field(max_length=200)
    email: str = Field(unique=True, index=True, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool = Field(default=True, index=True)


class Client(ClientBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClientCreate(ClientBase):
    pass


class ClientRead(ClientBase):
    id: int
    created_at: datetime


class ClientUpdate(SQLModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    is_active: bool | None = None
