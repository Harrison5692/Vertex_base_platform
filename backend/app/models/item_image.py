"""
Additional product images — retail-vertical addition. Item.image_url
stays what it always was: the single primary thumbnail used
everywhere an item is shown as a small card (storefront grid, cart
lines, receipts, order queue). This table is ADDITIONAL images for
the product detail page's gallery specifically — nothing else in the
app needs to know it exists. sort_order controls display order in the
gallery; the primary image_url is always shown first, ahead of
anything here.
"""

from sqlmodel import Field, SQLModel


class ItemImage(SQLModel, table=True):
    __tablename__ = "item_image"

    id: int | None = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="item.id", index=True)
    url: str = Field(max_length=1000)
    sort_order: int = Field(default=0)


class ItemImageCreate(SQLModel):
    url: str = Field(max_length=1000)
