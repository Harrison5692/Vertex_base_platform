"""
One-off seed script for a placeholder retail catalog — shirts, bags,
pins, patches — so a fresh deployment has something realistic-looking
to browse instead of an empty storefront. NOT a migration: this is
fixture data, not schema, and re-running it will create duplicates
(it doesn't check for existing rows) — run it once against a fresh
database, or clear the `item`/`item_image` tables first if re-running.

Images are placehold.co placeholders (clean colored boxes with the
product name as text) rather than fake stock photos — this is
explicitly a template catalog awaiting real product photography, and
pretending otherwise with stock images would be misleading once a
real store is live.

Usage (from the backend/ directory, or inside the backend container):
    python -m scripts.seed_retail_demo
"""

import asyncio

# Importing app.main pulls in every router, and transitively every
# model — including ones this script never touches directly (Account,
# Transaction, etc). SQLAlchemy needs every model that's referenced by
# a foreign key to actually be imported into memory before it can
# resolve relationships between tables; Item.account_id points at
# "account", so without this import the flush below fails with
# NoReferencedTableError even though the table exists in the database
# just fine. The real app never hits this because main.py already
# imports everything by the time any request comes in.
import app.main  # noqa: F401
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import engine
from app.models.item import Item
from app.models.item_image import ItemImage


def placeholder(text: str, bg: str, fg: str = "ffffff") -> str:
    return f"https://placehold.co/600x600/{bg}/{fg}?text={text.replace(' ', '+')}"


async def seed():
    async with AsyncSession(engine) as session:
        # --- Classic Tee (variants: S/M/L) ---
        tee = Item(
            name="Classic Tee",
            description="Midweight 100% cotton tee, relaxed fit. Runs true to size.",
            category="Apparel",
            image_url=placeholder("Classic Tee", "1a9c8f"),
            price=None,
            stock_quantity=None,
        )
        session.add(tee)
        await session.flush()

        for size, stock in [("Small", 20), ("Medium", 35), ("Large", 18)]:
            session.add(
                Item(
                    name=f"Classic Tee — {size}",
                    description=tee.description,
                    category="Apparel",
                    image_url=placeholder(f"Tee {size}", "1a9c8f"),
                    price=24.00,
                    sku=f"TEE-{size[0]}",
                    stock_quantity=stock,
                    low_stock_threshold=5,
                    variant_parent_id=tee.id,
                    variant_label=size,
                )
            )

        # --- Heavyweight Hoodie (variants: S/M/L/XL) ---
        hoodie = Item(
            name="Heavyweight Hoodie",
            description="Brushed fleece interior, kangaroo pocket, ribbed cuffs.",
            category="Apparel",
            image_url=placeholder("Hoodie", "334155"),
            price=None,
            stock_quantity=None,
        )
        session.add(hoodie)
        await session.flush()

        for size, stock in [("Small", 12), ("Medium", 22), ("Large", 15), ("X-Large", 8)]:
            session.add(
                Item(
                    name=f"Heavyweight Hoodie — {size}",
                    description=hoodie.description,
                    category="Apparel",
                    image_url=placeholder(f"Hoodie {size}", "334155"),
                    price=52.00,
                    sku=f"HOOD-{size[0]}",
                    stock_quantity=stock,
                    low_stock_threshold=5,
                    variant_parent_id=hoodie.id,
                    variant_label=size,
                )
            )

        # --- Standalone items (no variants) ---
        tote = Item(
            name="Canvas Tote Bag",
            description="Heavy 12oz canvas, reinforced handles, interior pocket.",
            category="Bags",
            image_url=placeholder("Canvas Tote", "b45309"),
            price=18.00,
            sku="TOTE-01",
            stock_quantity=40,
            low_stock_threshold=8,
        )
        session.add(tote)
        await session.flush()
        session.add(ItemImage(item_id=tote.id, url=placeholder("Tote Side", "b45309"), sort_order=0))
        session.add(ItemImage(item_id=tote.id, url=placeholder("Tote Inside", "b45309"), sort_order=1))

        session.add(
            Item(
                name="Crossbody Sling Bag",
                description="Lightweight everyday crossbody with adjustable strap.",
                category="Bags",
                image_url=placeholder("Sling Bag", "7c3aed"),
                price=34.00,
                sku="SLING-01",
                stock_quantity=4,
                low_stock_threshold=5,  # intentionally under threshold — demos the low-stock alert
            )
        )
        session.add(
            Item(
                name="Mini Canvas Pouch",
                description="Compact zip pouch, same canvas as the tote.",
                category="Bags",
                image_url=placeholder("Mini Pouch", "b45309"),
                price=14.00,
                sku="POUCH-01",
                stock_quantity=25,
                low_stock_threshold=5,
            )
        )
        session.add(
            Item(
                name="Cactus Enamel Pin",
                description="Hard enamel, gold plating, rubber clutch back.",
                category="Pins",
                image_url=placeholder("Cactus Pin", "16a34a"),
                price=9.00,
                sku="PIN-CACTUS",
                stock_quantity=60,
                low_stock_threshold=10,
            )
        )
        session.add(
            Item(
                name="Moon Phase Enamel Pin",
                description="Hard enamel, silver plating, rubber clutch back.",
                category="Pins",
                image_url=placeholder("Moon Pin", "1e3a8a"),
                price=9.00,
                sku="PIN-MOON",
                stock_quantity=60,
                low_stock_threshold=10,
            )
        )
        session.add(
            Item(
                name="Mountain Range Patch",
                description="Embroidered iron-on patch, 3in wide.",
                category="Patches",
                image_url=placeholder("Mountain Patch", "475569"),
                price=7.00,
                sku="PATCH-MTN",
                stock_quantity=50,
                low_stock_threshold=10,
            )
        )
        session.add(
            Item(
                name="Wave Embroidered Patch",
                description="Embroidered iron-on patch, 3in wide.",
                category="Patches",
                image_url=placeholder("Wave Patch", "0e7490"),
                price=7.00,
                sku="PATCH-WAVE",
                stock_quantity=50,
                low_stock_threshold=10,
            )
        )
        session.add(
            Item(
                name="Sticker Pack — Nature Set",
                description="5 die-cut vinyl stickers, weatherproof.",
                category="Stickers",
                image_url=placeholder("Sticker Pack", "ca8a04"),
                price=6.00,
                sku="STICK-NATURE",
                stock_quantity=3,
                low_stock_threshold=5,  # intentionally under threshold too
            )
        )

        await session.commit()
        print("Seeded placeholder catalog.")


if __name__ == "__main__":
    asyncio.run(seed())
