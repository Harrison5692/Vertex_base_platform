"""
History log — every meaningful business action, tied to the account
it involved (if any) and the account that performed it.

Transaction is the ORDER HEADER, not a single line item — it holds
who/when/how-paid/totals. The actual items sold live in
TransactionLine (see transaction_line.py), one row per item in the
sale, because a real sale is a cart of items, not one item per
checkout. This split is what "multi-item transaction" means.

account_id is nullable on purpose: a walk-in/guest purchase (retail,
a one-off cafe sale) has no account behind it at all. guest_label
holds a free-text name/note for that case ("walk-in", "cash sale"),
so the record isn't a bare null with no human-readable trace.

related_transaction_id links a refund/void back to the original sale
it reverses. This table is append-only — a refund is a NEW Transaction
row with type=refunded, never an edit of the original — so this FK is
what actually connects the two records instead of leaving someone to
guess by matching timestamps.

payment_method is deliberately a loose string enum, not a payment
processor integration — this base build doesn't compete with
Stripe/Square, it just records how the money moved. payment_reference
is where a real processor's charge/payment id would be stored once one
is wired in (see core/payments.py for the extension point) — nullable
because nothing populates it today.

subtotal/tax_amount/total are computed and stored at checkout time,
not derived on the fly — tax rates change, and a historical receipt
has to keep showing what was actually charged that day.

deposit_amount/balance_due are optional, added for staged-payment
cases (a deposit now, balance later) — a simple one-shot sale just
leaves both null.

shipping_* fields are a RETAIL-VERTICAL addition, not a base-build
concept — an in-person POS sale or a service appointment has no
shipping destination, so every field here is nullable and a non-retail
deployment simply never populates them. All optional at the model
level; the retail frontend enforces them as required before an
online (non-walk-in) order can be submitted.

Foreign keys are explicitly indexed here: Postgres does NOT auto-index
FK columns, only primary keys and unique constraints, so without this
every join/filter on account_id or created_at would be a full table
scan once there's real data volume.
"""

from datetime import datetime
from enum import Enum

from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class TransactionType(str, Enum):
    created = "created"
    updated = "updated"
    completed = "completed"
    cancelled = "cancelled"
    refunded = "refunded"
    voided = "voided"


class FulfillmentStatus(str, Enum):
    """Retail-vertical addition: where a completed online order stands
    in getting physically shipped. Distinct from TransactionType,
    which is about the financial event (a sale, a refund, a void) —
    a transaction can be financially `completed` while its physical
    order is still `pending`. Only meaningful for an online order (one
    with a shipping address); a staff walk-in POS sale has nothing to
    fulfill, so it's left null rather than forced through this
    pipeline. pending/processing/shipped/delivered are the normal
    forward path; cancelled is a terminal side-exit (e.g. staff
    catches a problem before it ships) — it does not reverse the sale
    itself, that's still what a refund is for."""

    pending = "pending"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


class PaymentMethod(str, Enum):
    cash = "cash"
    card = "card"
    bank_transfer = "bank_transfer"
    other = "other"


class TransactionBase(SQLModel):
    account_id: int | None = Field(default=None, foreign_key="account.id", index=True)
    guest_label: str | None = Field(default=None, max_length=200)
    # Retail-vertical: where to send the receipt for a guest checkout
    # (no account_id at all). Null whenever account_id is set — the
    # account's own email covers that case — and null for a staff
    # walk-in POS sale, which sends no receipt either way.
    guest_email: EmailStr | None = Field(default=None, max_length=255)
    type: TransactionType
    payment_method: PaymentMethod | None = Field(default=None)
    payment_reference: str | None = Field(default=None, max_length=255, index=True)
    notes: str | None = None
    related_transaction_id: int | None = Field(
        default=None, foreign_key="transaction.id", index=True
    )

    subtotal: float | None = Field(default=None)
    tax_amount: float | None = Field(default=None)
    total: float | None = Field(default=None)

    # Staged payments — a deposit now, balance later.
    # Both null for a simple one-shot sale.
    deposit_amount: float | None = Field(default=None)
    balance_due: float | None = Field(default=None)

    # Retail-vertical: shipping destination for an online order.
    # Null for a walk-in/POS sale or any non-retail deployment.
    shipping_name: str | None = Field(default=None, max_length=200)
    shipping_line1: str | None = Field(default=None, max_length=255)
    shipping_line2: str | None = Field(default=None, max_length=255)
    shipping_city: str | None = Field(default=None, max_length=100)
    shipping_state: str | None = Field(default=None, max_length=100)
    shipping_postal_code: str | None = Field(default=None, max_length=20)
    shipping_country: str | None = Field(default=None, max_length=100)
    shipping_phone: str | None = Field(default=None, max_length=30)

    # Server-assigned only (see TransactionCreate below for why it's
    # not client-settable at creation) — set once at checkout, then
    # only ever changed via PATCH /transactions/{id}/fulfillment.
    fulfillment_status: FulfillmentStatus | None = Field(default=None, index=True)


class Transaction(TransactionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # Nullable: a guest checkout (no account at all, see guest_email
    # above) has no account to attribute creation to. Every other path
    # — staff POS sale, logged-in customer checkout, refund — still
    # always sets this.
    created_by: int | None = Field(default=None, foreign_key="account.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class TransactionCreate(SQLModel):
    """Deliberately NOT inheriting TransactionBase — that would expose
    subtotal/tax_amount/total (server-computed, silently overwritten
    anyway) and related_transaction_id (system-managed only, set by
    the /refund endpoint — a client should never be able to claim a
    transaction is a refund of another one just by setting this field
    on creation). Only fields a client should legitimately supply
    live here."""

    account_id: int | None = None
    guest_label: str | None = None
    guest_email: EmailStr | None = None
    type: TransactionType
    payment_method: PaymentMethod | None = None
    notes: str | None = None
    deposit_amount: float | None = None
    balance_due: float | None = None

    # Retail-vertical: only sent by the online storefront checkout,
    # left null by a staff-run walk-in POS sale.
    shipping_name: str | None = None
    shipping_line1: str | None = None
    shipping_line2: str | None = None
    shipping_city: str | None = None
    shipping_state: str | None = None
    shipping_postal_code: str | None = None
    shipping_country: str | None = None
    shipping_phone: str | None = None

    # Set by the storefront's Stripe Elements form (a Stripe
    # PaymentMethod id, e.g. "pm_..." — never a raw card number,
    # Stripe.js exchanges the typed card for this token before it
    # ever reaches this server). Only meaningful when payment_method
    # is "card" and a real Stripe key is configured; a staff-run POS
    # sale recording an already-swiped card leaves this null and
    # behaves exactly as it always has.
    stripe_payment_method_id: str | None = None


class TransactionRead(TransactionBase):
    id: int
    created_by: int | None
    created_at: datetime
