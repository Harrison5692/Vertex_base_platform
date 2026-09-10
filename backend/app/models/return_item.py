"""
Returns/restock tracking — retail-vertical addition.

A refund (see /transactions/{id}/refund) is a MONEY decision — it
doesn't itemize which physical items are coming back, by design (see
that endpoint's docstring). Whether an item is even coming back
physically, and what happens to it once it does, is a SEPARATE
decision this table tracks: a returned item sits in
`pending_inspection` until staff decide its fate —

- restocked: goes back into the original item's stock_quantity as-is
- restocked_discounted: goes back at a lower price, as its own Item
  row (see Item.parent_item_id) rather than changing the original
  item's price for everyone
- discarded: no stock change at all

ReturnRequest is the header (which refund this return traces back
to); ReturnLine is one row per item/quantity coming back, since a
single refund can involve several different items. Resolution
(restocked/discounted/discarded) happens per LINE, not per request —
different items from the same return can end up resolved differently
(one resold, one discarded for damage).
"""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class ReturnLineStatus(str, Enum):
    pending_inspection = "pending_inspection"
    restocked = "restocked"
    restocked_discounted = "restocked_discounted"
    discarded = "discarded"


class ReturnRequestBase(SQLModel):
    refund_transaction_id: int = Field(foreign_key="transaction.id", index=True)
    notes: str | None = None


class ReturnRequest(ReturnRequestBase, table=True):
    __tablename__ = "return_request"

    id: int | None = Field(default=None, primary_key=True)
    created_by: int = Field(foreign_key="account.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ReturnLineBase(SQLModel):
    item_id: int = Field(foreign_key="item.id", index=True)
    quantity: int = Field(gt=0)


class ReturnLine(ReturnLineBase, table=True):
    __tablename__ = "return_line"

    id: int | None = Field(default=None, primary_key=True)
    return_request_id: int = Field(foreign_key="return_request.id", index=True)
    status: ReturnLineStatus = Field(default=ReturnLineStatus.pending_inspection, index=True)
    # Set only when status becomes restocked_discounted — the new
    # (or reused) Item row the returned units were added to.
    discount_item_id: int | None = Field(default=None, foreign_key="item.id")
    resolved_at: datetime | None = Field(default=None)
    resolved_by: int | None = Field(default=None, foreign_key="account.id")


class ReturnLineCreate(ReturnLineBase):
    pass


class ReturnLineRead(ReturnLineBase):
    id: int
    return_request_id: int
    status: ReturnLineStatus
    discount_item_id: int | None
    resolved_at: datetime | None
    resolved_by: int | None


class ReturnRequestCreate(ReturnRequestBase):
    lines: list[ReturnLineCreate]


class ReturnRequestRead(ReturnRequestBase):
    id: int
    created_by: int
    created_at: datetime
    lines: list[ReturnLineRead] = []


class ResolveReturnLineRequest(SQLModel):
    status: ReturnLineStatus
    # Required when status is restocked_discounted, ignored otherwise.
    discount_price: float | None = Field(default=None, ge=0)
