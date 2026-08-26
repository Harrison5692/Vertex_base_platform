"""
History log — every meaningful business action, tied to the account
it involved (if any) and the account that performed it.

Transaction is the ORDER HEADER, not a single line item — it holds
who/when/how-paid/totals. The actual items sold live in
TransactionLine (see transaction_line.py), one row per item in the
sale, because a real sale is a cart of items, not one item per
checkout. This split is what "multi-item transaction" means:
account_id is nullable on purpose: a walk-in/guest purchase (retail,
a one-off cafe sale) has no account behind it at all. guest_label
holds a free-text name/note for that case ("walk-in", "cash sale"),
so the record isn't a bare null with no human-readable trace.

payment_method is deliberately a loose string enum, not a payment
processor integration — this base build doesn't compete with
Stripe/Square, it just records how the money moved.

subtotal/tax_amount/total are computed and stored at checkout time,
not derived on the fly — tax rates change, and a historical receipt
has to keep showing what was actually charged that day.

deposit_amount/balance_due are optional, added for staged-payment
cases (a deposit now, balance later) — a simple one-shot sale just
leaves both null.

Foreign keys are explicitly indexed here: Postgres does NOT auto-index
FK columns, only primary keys and unique constraints, so without this
every join/filter on account_id or created_at would be a full table
scan once there's real data volume.
"""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class TransactionType(str, Enum):
    created = "created"
    updated = "updated"
    completed = "completed"
    cancelled = "cancelled"
    refunded = "refunded"
    voided = "voided"


class PaymentMethod(str, Enum):
    cash = "cash"
    card = "card"
    bank_transfer = "bank_transfer"
    other = "other"


class TransactionBase(SQLModel):
    account_id: int | None = Field(default=None, foreign_key="account.id", index=True)
    guest_label: str | None = Field(default=None, max_length=200)
    type: TransactionType
    payment_method: PaymentMethod | None = Field(default=None)
    notes: str | None = None

    subtotal: float | None = Field(default=None)
    tax_amount: float | None = Field(default=None)
    total: float | None = Field(default=None)

    # Staged payments — a deposit now, balance later.
    # Both null for a simple one-shot sale.
    deposit_amount: float | None = Field(default=None)
    balance_due: float | None = Field(default=None)


class Transaction(TransactionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_by: int = Field(foreign_key="account.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class TransactionCreate(TransactionBase):
    pass


class TransactionRead(TransactionBase):
    id: int
    created_by: int
    created_at: datetime
