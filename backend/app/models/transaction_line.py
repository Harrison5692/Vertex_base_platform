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

from sqlmodel import Field, SQLModel


class TransactionLineBase(SQLModel):
    transaction_id: int = Field(foreign_key="transaction.id", index=True)
    item_id: int = Field(foreign_key="item.id", index=True)
    quantity: int = Field(default=1)
    unit_price: float
    line_total: float


class TransactionLine(TransactionLineBase, table=True):
    __tablename__ = "transaction_line"

    id: int | None = Field(default=None, primary_key=True)


class TransactionLineCreate(SQLModel):
    """Shape used when creating a transaction with its line items —
    no transaction_id here since it's assigned server-side after the
    parent Transaction is created."""

    item_id: int
    quantity: int = 1
    unit_price: float


class TransactionLineRead(TransactionLineBase):
    id: int
