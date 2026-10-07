"""Promo codes: the rules (pure) and the full checkout path (database)."""

from datetime import datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.discounts import DiscountError, check_discount
from app.db import session as db_session
from app.models.discount_code import DiscountCode, DiscountKind
from tests.test_checkout_pricing import _auth, _make_account, _make_item, _order

NOW = datetime(2026, 10, 7, 12, 0)


def _dc(**kw) -> DiscountCode:
    base = dict(code="TEST", kind=DiscountKind.percent, value=10, uses_count=0, is_active=True)
    return DiscountCode(**{**base, **kw})


# --- rules, no database -----------------------------------------------------


def test_percent():
    assert check_discount(_dc(value=15), 40.0, NOW) == 6.0


def test_fixed_capped_at_subtotal():
    assert check_discount(_dc(kind=DiscountKind.fixed, value=10), 6.0, NOW) == 6.0


@pytest.mark.parametrize(
    ("dc", "subtotal", "message"),
    [
        (None, 20, "isn't valid"),
        (_dc(is_active=False), 20, "isn't valid"),
        (_dc(starts_at=NOW + timedelta(days=1)), 20, "isn't active yet"),
        (_dc(expires_at=NOW - timedelta(seconds=1)), 20, "expired"),
        (_dc(max_uses=3, uses_count=3), 20, "usage limit"),
        (_dc(min_subtotal=25), 20, r"at least \$25\.00"),
    ],
)
def test_rejections(dc, subtotal, message):
    with pytest.raises(DiscountError, match=message):
        check_discount(dc, subtotal, NOW)


# --- through the API --------------------------------------------------------

pytestmark_db = pytest.mark.asyncio


async def _save(dc: DiscountCode) -> DiscountCode:
    async with AsyncSession(db_session.engine) as s:
        s.add(dc)
        await s.commit()
        await s.refresh(dc)
        return dc


async def _uses(code_id: int) -> int:
    async with AsyncSession(db_session.engine) as s:
        return (await s.get(DiscountCode, code_id)).uses_count


@pytestmark_db
async def test_checkout_applies_code_case_insensitively_and_counts_use(client):
    dc = await _save(_dc(code="SAVE10", value=10))
    item = await _make_item(price=40.0)
    r = await client.post("/transactions/", json=_order(item.id, discount_code=" save10 "))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["discount_code"] == "SAVE10"
    assert body["discount_amount"] == 4.0
    assert body["subtotal"] == 40.0
    assert await _uses(dc.id) == 1


@pytestmark_db
async def test_quote_matches_checkout_with_code(client):
    await _save(_dc(code="FIVE", kind=DiscountKind.fixed, value=5))
    item = await _make_item(price=30.0)
    q = await client.post(
        "/transactions/quote",
        json={
            "lines": [{"item_id": item.id, "quantity": 1}],
            "shipping_country": "US",
            "shipping_state": "TX",
            "discount_code": "five",
        },
    )
    r = await client.post("/transactions/", json=_order(item.id, discount_code="five"))
    assert q.status_code == 200 and r.status_code == 201, (q.text, r.text)
    assert q.json()["discount"] == 5.0
    assert q.json()["total"] == r.json()["total"]


@pytestmark_db
async def test_invalid_code_quote_still_prices_cart(client):
    item = await _make_item(price=30.0)
    q = await client.post(
        "/transactions/quote",
        json={"lines": [{"item_id": item.id}], "shipping_state": "TX", "discount_code": "NOPE"},
    )
    assert q.status_code == 200
    assert q.json()["discount"] == 0
    assert "isn't valid" in q.json()["discount_code_error"]


@pytestmark_db
async def test_invalid_code_checkout_is_a_field_error_and_nothing_saved(client):
    item = await _make_item(price=30.0)
    r = await client.post("/transactions/", json=_order(item.id, discount_code="NOPE"))
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "discount_code"]
    assert (await client.post("/transactions/quote", json={"lines": []})).status_code == 200


@pytestmark_db
async def test_max_uses_enforced(client):
    await _save(_dc(code="ONCE", max_uses=1))
    item = await _make_item(price=20.0, stock=10)
    first = await client.post("/transactions/", json=_order(item.id, discount_code="ONCE"))
    second = await client.post("/transactions/", json=_order(item.id, discount_code="ONCE"))
    assert first.status_code == 201, first.text
    assert second.status_code == 422
    assert "usage limit" in second.json()["detail"][0]["msg"]


@pytestmark_db
async def test_manager_can_create_and_deactivate_staff_cannot(client):
    manager = await _make_account("mgr2@example.com", tier=3)
    staff = await _make_account("staff3@example.com", tier=2)
    payload = {"code": "fall15", "kind": "percent", "value": 15}

    assert (await client.post("/discount-codes/", json=payload, headers=_auth(staff))).status_code == 403
    r = await client.post("/discount-codes/", json=payload, headers=_auth(manager))
    assert r.status_code == 201, r.text
    assert r.json()["code"] == "FALL15"

    dup = await client.post("/discount-codes/", json=payload, headers=_auth(manager))
    assert dup.status_code == 409

    off = await client.patch(
        f"/discount-codes/{r.json()['id']}", json={"is_active": False}, headers=_auth(manager)
    )
    assert off.status_code == 200 and off.json()["is_active"] is False


@pytestmark_db
async def test_percent_over_100_rejected(client):
    manager = await _make_account("mgr3@example.com", tier=3)
    r = await client.post(
        "/discount-codes/",
        json={"code": "TOOMUCH", "kind": "percent", "value": 150},
        headers=_auth(manager),
    )
    assert r.status_code == 422


@pytestmark_db
async def test_street_number_required_at_checkout(client):
    item = await _make_item()
    r = await client.post("/transactions/", json=_order(item.id, shipping_line1="John"))
    assert r.status_code == 422
    assert "street number" in r.json()["detail"]
