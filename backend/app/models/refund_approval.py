"""
Refund approval gate — retail-vertical addition.

A refund is no longer something any staff member can trigger
instantly (see api/transactions.py's old /refund endpoint, now
manager-only as a documented direct override). The normal path is:
staff logs a RefundApproval request (what the customer is claiming,
and roughly what they'll need to show — damage, unopened return,
etc.), a manager reviews it and either approves (money actually
moves, via api/transactions.py's shared _issue_refund) or denies it
(with a reason). Nothing about stock or payment changes until that
review happens.

30-day window is enforced at request-creation time against the
original transaction's created_at, not configurable per-request —
if a deployment needs a different window, this is the one place to
change it.
"""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class RefundApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    denied = "denied"


class RefundApprovalBase(SQLModel):
    original_transaction_id: int = Field(foreign_key="transaction.id", index=True)
    reason: str | None = Field(default=None, max_length=1000)
    # Null = full refund of the original total, decided at review time.
    requested_amount: float | None = Field(default=None, ge=0)


class RefundApproval(RefundApprovalBase, table=True):
    __tablename__ = "refund_approval"

    id: int | None = Field(default=None, primary_key=True)
    status: RefundApprovalStatus = Field(default=RefundApprovalStatus.pending, index=True)
    requested_by: int = Field(foreign_key="account.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    reviewed_by: int | None = Field(default=None, foreign_key="account.id")
    reviewed_at: datetime | None = Field(default=None)
    # The "proof" — required either way: why this was approved (item
    # confirmed returned/damaged) or denied (outside window, no proof
    # provided, etc). Free text — this template has no file-upload
    # flow for photos of damage.
    review_notes: str | None = Field(default=None, max_length=1000)
    resulting_transaction_id: int | None = Field(default=None, foreign_key="transaction.id")


class RefundApprovalCreate(RefundApprovalBase):
    pass


class RefundApprovalRead(RefundApprovalBase):
    id: int
    status: RefundApprovalStatus
    requested_by: int
    created_at: datetime
    reviewed_by: int | None
    reviewed_at: datetime | None
    review_notes: str | None
    resulting_transaction_id: int | None


class ReviewRefundApprovalRequest(SQLModel):
    approve: bool
    notes: str = Field(min_length=1, max_length=1000)
    # Only meaningful when approve=True; overrides requested_amount
    # for this specific approval if a manager decides on a different
    # figure than what was asked for.
    amount: float | None = Field(default=None, gt=0)
