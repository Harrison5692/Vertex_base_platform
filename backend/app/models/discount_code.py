"""
Retail-vertical: promo codes a customer types at checkout.

Two kinds, deliberately nothing fancier yet: percent off the
merchandise subtotal, or a fixed dollar amount off it (capped at the
subtotal — a $10 code on a $6 order takes $6, never goes negative).
The discount applies BEFORE shipping and tax: shipping tiers and the
free-shipping threshold look at the discounted subtotal, so a 50%-off
code on a $60 cart doesn't also unlock free shipping meant for $50+
orders, and tax is charged on what the customer actually pays.

code is stored upper-cased and matched case-insensitively ("summer10"
== "SUMMER10"). uses_count is incremented inside the checkout's own
database transaction with the row locked, so max_uses can't be
overshot by two simultaneous checkouts.

Codes are deactivated rather than deleted: past orders record the
code string they used, and keeping the row keeps that history
readable.
"""

from datetime import datetime
from enum import Enum

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class DiscountKind(str, Enum):
    percent = "percent"
    fixed = "fixed"


class DiscountCodeBase(SQLModel):
    code: str = Field(max_length=50, unique=True, index=True)
    kind: DiscountKind
    # percent: 1-100 (e.g. 15 = 15% off). fixed: dollars off.
    value: float = Field(gt=0)
    # Optional rules — null means "no restriction".
    min_subtotal: float | None = Field(default=None, ge=0)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    max_uses: int | None = Field(default=None, ge=1)
    is_active: bool = Field(default=True)


class DiscountCode(DiscountCodeBase, table=True):
    __tablename__ = "discount_code"
    __table_args__ = (
        sa.CheckConstraint("value > 0", name="ck_discount_code_value_positive"),
        sa.CheckConstraint(
            "kind != 'percent' OR value <= 100", name="ck_discount_code_percent_max_100"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    uses_count: int = Field(default=0, ge=0)
    created_by: int | None = Field(default=None, foreign_key="account.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DiscountCodeCreate(DiscountCodeBase):
    pass


class DiscountCodeUpdate(SQLModel):
    value: float | None = Field(default=None, gt=0)
    min_subtotal: float | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    max_uses: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class DiscountCodeRead(DiscountCodeBase):
    id: int
    uses_count: int
    created_at: datetime
