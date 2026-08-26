"""
Item — the general "thing the business sells or tracks" entity.
Fields beyond `name`/`description` are all optional on purpose:
- price/sku/stock_quantity: POS and retail
- duration_minutes: services (massage, pressure washing) and
  catering (used alongside price for a package)
A pure POS business just leaves duration_minutes null; a pure
service business leaves sku/stock_quantity null. One table, several
business types, no schema fork needed.

Optionally tied to an Account via account_id — e.g. a purchase, work
order, or service record belonging to a specific tier-1 client.
Nullable, since not every business's "item" is client-specific (some
are just internal inventory/records with no owner).
"""

from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class ItemBase(SQLModel):
    name: str = Field(index=True, max_length=200)
    description: str | None = None
    category: str | None = Field(default=None, index=True, max_length=100)
    is_active: bool = Field(default=True, index=True)
    account_id: int | None = Field(default=None, foreign_key="account.id", index=True)

    # POS / retail
    price: float | None = Field(default=None, ge=0)
    sku: str | None = Field(default=None, unique=True, index=True, max_length=100)
    stock_quantity: int | None = Field(default=None, ge=0)

    # Services / catering
    duration_minutes: int | None = Field(default=None)


class Item(ItemBase, table=True):
    """Actual database table. __table_args__ enforces price/stock at
    the database level, not just via Pydantic validation on the API
    layer — defense-in-depth for a shared template other services may
    write to directly."""

    __table_args__ = (
        sa.CheckConstraint("price IS NULL OR price >= 0", name="ck_item_price_non_negative"),
        sa.CheckConstraint(
            "stock_quantity IS NULL OR stock_quantity >= 0",
            name="ck_item_stock_quantity_non_negative",
        ),
    )

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
    category: str | None = None
    is_active: bool | None = None
    price: float | None = Field(default=None, ge=0)
    sku: str | None = None
    stock_quantity: int | None = Field(default=None, ge=0)
    duration_minutes: int | None = None
