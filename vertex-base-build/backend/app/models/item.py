"""
Example domain entity — replace with the client's actual tracked
records (patients, orders, work tickets, whatever the business runs on).

Optionally tied to an Account via account_id — e.g. a purchase, work
order, or service record belonging to a specific tier-1 client.
Nullable, since not every business's "item" is client-specific (some
are just internal inventory/records with no owner).

This demonstrates the pattern the whole template follows: a shared
Base class holds the fields, a `table=True` subclass becomes the
actual DB table, and lightweight subclasses become the API's
request/response shapes. One source of truth per field instead of
a separate SQLAlchemy model + several Pydantic schemas.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class ItemBase(SQLModel):
    name: str = Field(index=True, max_length=200)
    description: str | None = None
    is_active: bool = Field(default=True, index=True)
    account_id: int | None = Field(default=None, foreign_key="account.id", index=True)


class Item(ItemBase, table=True):
    """Actual database table."""

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ItemCreate(ItemBase):
    """Shape expected on POST /items."""

    pass


class ItemRead(ItemBase):
    """Shape returned to the client — includes server-generated fields."""

    id: int
    created_at: datetime
    updated_at: datetime


class ItemUpdate(SQLModel):
    """All fields optional — partial updates via PATCH."""

    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
