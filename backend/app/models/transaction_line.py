"""
One row per item in a Transaction (order header). A transaction with
3 items in the cart is 1 Transaction row + 3 TransactionLine rows —
this is what makes multi-item sales possible instead of forcing one
checkout per item.

unit_price is a snapshot taken at sale time — Item.price can change
later, and a historical line item must keep showing what was
actually charged that day, not today's price. line_total is stored
rather than computed on read for the same reason: it's a receipt,
not a live calculation.
"""

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class TransactionLineBase(SQLModel):
    transaction_id: int = Field(foreign_key="transaction.id", index=True)
    item_id: int = Field(foreign_key="item.id", index=True)
    quantity: int = Field(default=1, ge=1)
    unit_price: float = Field(ge=0)
    line_total: float = Field(ge=0)


class TransactionLine(TransactionLineBase, table=True):
    """__table_args__ enforces the same bounds at the database level
    as TransactionLineCreate does via Pydantic — defense-in-depth."""

    __tablename__ = "transaction_line"
    __table_args__ = (
        sa.CheckConstraint("quantity >= 1", name="ck_transaction_line_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_transaction_line_unit_price_non_negative"),
        sa.CheckConstraint("line_total >= 0", name="ck_transaction_line_line_total_non_negative"),
    )

    id: int | None = Field(default=None, primary_key=True)


class TransactionLineCreate(SQLModel):
    """Shape used when creating a transaction with its line items —
    no transaction_id here since it's assigned server-side after the
    parent Transaction is created."""

    item_id: int
    quantity: int = Field(default=1, ge=1)
    unit_price: float = Field(ge=0)


class TransactionLineRead(TransactionLineBase):
    id: int
