"""
Server-side cart — retail-vertical addition, only for logged-in
accounts. A guest (not logged in) still uses localStorage in the
browser, which already persists across visits in the SAME browser;
this exists specifically so a logged-in customer's cart follows them
across devices/browsers, which localStorage can never do on its own.

One row per (account, item) — quantity holds the count, no separate
"line id" concept the client needs to track. Whole-cart-replace
(PUT /cart/) rather than a per-line CRUD API, matching how the
frontend already treated the cart as a single array whether it lived
in localStorage or here.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class CartItem(SQLModel, table=True):
    __tablename__ = "cart_item"

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    item_id: int = Field(foreign_key="item.id", index=True)
    quantity: int = Field(gt=0)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CartLineIn(SQLModel):
    item_id: int
    quantity: int = Field(gt=0)


class CartReplaceRequest(SQLModel):
    lines: list[CartLineIn]


class CartLineOut(SQLModel):
    item_id: int
    quantity: int
    name: str
    unit_price: float | None
    image_url: str | None
