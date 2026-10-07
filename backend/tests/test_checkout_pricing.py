"""
End-to-end checkout through the real API and a real (test) database.
Uses whatever shipping/tax client.config.json holds, read from
client_config — so these assert the relationships (tiers, tax on
shipping, server-side prices), with expected numbers computed from
the same config the server uses.
"""

import pytest

from app.core.client_config import client_config
from app.core.pricing import compute_totals
from app.core.security import create_access_token, hash_password
from app.db import session as db_session
from app.models.account import Account
from app.models.item import Item
from sqlmodel.ext.asyncio.session import AsyncSession

pytestmark = pytest.mark.asyncio

ADDRESS = {
    "shipping_name": "Test Buyer",
    "shipping_line1": "1 Main St",
    "shipping_city": "Houston",
    "shipping_state": "TX",
    "shipping_postal_code": "77002",
    "shipping_country": "US",
}


async def _make_item(name="Shirt", price=20.0, stock=10, **extra) -> Item:
    async with AsyncSession(db_session.engine) as s:
        item = Item(name=name, price=price, stock_quantity=stock, **extra)
        s.add(item)
        await s.commit()
        await s.refresh(item)
        return item


async def _make_account(email, tier) -> Account:
    async with AsyncSession(db_session.engine) as s:
        acct = Account(email=email, tier=tier, hashed_password=hash_password("pw-12345678"))
        s.add(acct)
        await s.commit()
        await s.refresh(acct)
        return acct


def _auth(account: Account) -> dict:
    return {"Authorization": f"Bearer {create_access_token(account.email)}"}


def _order(item_id, qty=1, unit_price=0.01, **overrides):
    return {
        "type": "completed",
        "payment_method": "card",
        "guest_email": "guest@example.com",
        "lines": [{"item_id": item_id, "quantity": qty, "unit_price": unit_price}],
        **ADDRESS,
        **overrides,
    }


async def test_guest_pays_catalog_price_not_client_price(client):
    item = await _make_item(price=20.0)
    # Client claims $0.01 — server must ignore it.
    r = await client.post("/transactions/", json=_order(item.id, qty=2, unit_price=0.01))
    assert r.status_code == 201, r.text
    body = r.json()
    expected = compute_totals(40.0, online=True, state="TX", config=client_config)
    assert body["lines"][0]["unit_price"] == 20.0
    assert body["subtotal"] == 40.0
    assert body["shipping_amount"] == expected.shipping
    assert body["tax_amount"] == expected.tax
    assert body["total"] == expected.total


async def test_guest_cannot_override_tax(client):
    item = await _make_item(price=20.0)
    r = await client.post("/transactions/", json=_order(item.id, tax_amount=0))
    assert r.status_code == 201, r.text
    expected = compute_totals(20.0, online=True, state="TX", config=client_config)
    assert r.json()["tax_amount"] == expected.tax


async def test_quote_matches_checkout(client):
    item = await _make_item(price=7.5)
    q = await client.post(
        "/transactions/quote",
        json={
            "lines": [{"item_id": item.id, "quantity": 1}],
            "online": True,
            "shipping_country": "US",
            "shipping_state": "TX",
        },
    )
    assert q.status_code == 200, q.text
    r = await client.post("/transactions/", json=_order(item.id))
    assert r.status_code == 201, r.text
    quote, order = q.json(), r.json()
    assert quote["total"] == order["total"]
    assert quote["shipping"] == order["shipping_amount"]
    assert quote["tax"] == order["tax_amount"]


async def test_rejects_non_us_address(client):
    item = await _make_item()
    r = await client.post(
        "/transactions/", json=_order(item.id, shipping_country="Canada", shipping_state="ON")
    )
    assert r.status_code == 422
    assert "only ship to" in r.json()["detail"]


async def test_state_is_normalized_on_the_order(client):
    item = await _make_item()
    r = await client.post(
        "/transactions/", json=_order(item.id, shipping_country="usa", shipping_state="tx")
    )
    assert r.status_code == 201, r.text
    assert r.json()["shipping_country"] == "US"
    assert r.json()["shipping_state"] == "TX"


async def test_customer_must_ship(client):
    item = await _make_item()
    order = _order(item.id)
    for key in ADDRESS:
        order.pop(key)
    r = await client.post("/transactions/", json=order)
    assert r.status_code == 422


async def test_customer_cannot_create_refund_rows(client):
    item = await _make_item()
    r = await client.post("/transactions/", json=_order(item.id, type="refunded"))
    assert r.status_code == 403


async def test_customer_cannot_attach_order_to_another_account(client):
    victim = await _make_account("victim@example.com", tier=1)
    buyer = await _make_account("buyer@example.com", tier=1)
    item = await _make_item()
    r = await client.post(
        "/transactions/",
        json=_order(item.id, account_id=victim.id, guest_email=None),
        headers=_auth(buyer),
    )
    assert r.status_code == 201, r.text
    assert r.json()["account_id"] == buyer.id


async def test_inactive_or_unpriced_item_rejected(client):
    unpriced = await _make_item(name="No price", price=None)
    r = await client.post("/transactions/", json=_order(unpriced.id))
    assert r.status_code == 422


async def test_staff_walk_in_sale_keeps_manual_price_and_tax_override(client):
    staff = await _make_account("staff@example.com", tier=2)
    item = await _make_item(price=20.0)
    r = await client.post(
        "/transactions/",
        json={
            "type": "completed",
            "payment_method": "cash",
            "guest_label": "Walk-in",
            "tax_amount": 0,
            "lines": [{"item_id": item.id, "quantity": 1, "unit_price": 15.0}],
        },
        headers=_auth(staff),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["subtotal"] == 15.0
    assert body["shipping_amount"] is None
    assert body["tax_amount"] == 0.0
    assert body["total"] == 15.0
    assert body["fulfillment_status"] is None


async def test_staff_walk_in_default_tax_is_in_store_rate(client):
    staff = await _make_account("staff2@example.com", tier=2)
    item = await _make_item(price=20.0)
    r = await client.post(
        "/transactions/",
        json={
            "type": "completed",
            "payment_method": "cash",
            "lines": [{"item_id": item.id, "quantity": 1, "unit_price": 20.0}],
        },
        headers=_auth(staff),
    )
    assert r.status_code == 201, r.text
    expected = compute_totals(20.0, online=False, state=None, config=client_config)
    assert r.json()["tax_amount"] == expected.tax


async def test_full_refund_includes_shipping(client):
    manager = await _make_account("mgr@example.com", tier=3)
    item = await _make_item(price=20.0)
    order = (await client.post("/transactions/", json=_order(item.id))).json()
    r = await client.post(
        f"/transactions/{order['id']}/refund", json={}, headers=_auth(manager)
    )
    assert r.status_code == 201, r.text
    assert r.json()["total"] == -order["total"]


async def test_stripe_configured_requires_card_for_customers(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")
    item = await _make_item()
    r = await client.post("/transactions/", json=_order(item.id, payment_method="cash"))
    assert r.status_code == 422
    assert "Card payment is required" in r.json()["detail"]
