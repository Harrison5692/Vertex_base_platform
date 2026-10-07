"""No refund without a manager; nobody escalates their own access."""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.client_config import client_config
from app.db import session as db_session
from app.models.refund_approval import RefundApproval
from app.models.transaction import Transaction, TransactionType
from tests.test_checkout_pricing import _auth, _make_account, _make_item, _order

pytestmark = pytest.mark.asyncio


async def _refunds_for(tx_id):
    async with AsyncSession(db_session.engine) as s:
        rows = await s.exec(
            select(Transaction).where(
                Transaction.related_transaction_id == tx_id,
                Transaction.type == TransactionType.refunded,
            )
        )
        return rows.all()


async def _approvals_for(tx_id):
    async with AsyncSession(db_session.engine) as s:
        rows = await s.exec(
            select(RefundApproval).where(RefundApproval.original_transaction_id == tx_id)
        )
        return rows.all()


async def _place(client, price=20.0, stock=5):
    item = await _make_item(price=price, stock=stock)
    r = await client.post("/transactions/", json=_order(item.id))
    assert r.status_code == 201, r.text
    return r.json(), item


# --- cancellations ----------------------------------------------------------


async def test_staff_cancel_restocks_but_only_requests_refund(client):
    staff = await _make_account("s@example.com", tier=2)
    order, item = await _place(client, stock=5)
    r = await client.patch(
        f"/transactions/{order['id']}/fulfillment",
        json={"status": "cancelled"},
        headers=_auth(staff),
    )
    assert r.status_code == 200, r.text
    assert await _refunds_for(order["id"]) == []  # no money moved
    approvals = await _approvals_for(order["id"])
    assert len(approvals) == 1
    assert approvals[0].status == "pending"
    assert approvals[0].requested_amount == order["total"]
    stock = (await client.get(f"/items/{item.id}")).json()["stock_quantity"]
    assert stock == 5  # back in stock immediately


async def test_manager_approves_staff_cancellation(client):
    staff = await _make_account("s2@example.com", tier=2)
    manager = await _make_account("m2@example.com", tier=3)
    order, _ = await _place(client)
    await client.patch(
        f"/transactions/{order['id']}/fulfillment",
        json={"status": "cancelled"},
        headers=_auth(staff),
    )
    approval = (await _approvals_for(order["id"]))[0]
    r = await client.patch(
        f"/refund-approvals/{approval.id}/review",
        json={"approve": True, "notes": "Confirmed cancelled before shipping"},
        headers=_auth(manager),
    )
    assert r.status_code == 200, r.text
    refunds = await _refunds_for(order["id"])
    assert len(refunds) == 1 and refunds[0].total == -order["total"]


async def test_manager_cancel_refunds_immediately(client):
    manager = await _make_account("m3@example.com", tier=3)
    order, _ = await _place(client)
    r = await client.patch(
        f"/transactions/{order['id']}/fulfillment",
        json={"status": "cancelled"},
        headers=_auth(manager),
    )
    assert r.status_code == 200, r.text
    assert len(await _refunds_for(order["id"])) == 1
    assert await _approvals_for(order["id"]) == []


async def test_staff_cannot_issue_direct_refund(client):
    staff = await _make_account("s4@example.com", tier=2)
    order, _ = await _place(client)
    r = await client.post(f"/transactions/{order['id']}/refund", json={}, headers=_auth(staff))
    assert r.status_code == 403


# --- refund window follows config --------------------------------------------


async def test_refund_window_comes_from_config(client, monkeypatch):
    customer = await _make_account("c@example.com", tier=1)
    item = await _make_item()
    order = (
        await client.post(
            "/transactions/", json=_order(item.id, guest_email=None), headers=_auth(customer)
        )
    ).json()
    monkeypatch.setitem(client_config, "policies", {"return_window_days": 0})
    r = await client.post(
        "/refund-approvals/",
        json={"original_transaction_id": order["id"], "reason": "changed mind"},
        headers=_auth(customer),
    )
    assert r.status_code == 422
    assert "0-day" in r.json()["detail"]


# --- tiers -------------------------------------------------------------------


async def test_staff_cannot_change_tiers(client):
    staff = await _make_account("s5@example.com", tier=2)
    customer = await _make_account("c5@example.com", tier=1)
    r = await client.patch(f"/accounts/{customer.id}", json={"tier": 2}, headers=_auth(staff))
    assert r.status_code == 403


async def test_nobody_promotes_themselves(client):
    staff = await _make_account("s6@example.com", tier=2)
    manager = await _make_account("m6@example.com", tier=3)
    assert (
        await client.patch(f"/accounts/{staff.id}", json={"tier": 3}, headers=_auth(staff))
    ).status_code == 403
    assert (
        await client.patch(f"/accounts/{manager.id}", json={"tier": 4}, headers=_auth(manager))
    ).status_code == 403


async def test_manager_can_promote_up_to_own_level_only(client):
    manager = await _make_account("m7@example.com", tier=3)
    customer = await _make_account("c7@example.com", tier=1)
    ok = await client.patch(f"/accounts/{customer.id}", json={"tier": 2}, headers=_auth(manager))
    assert ok.status_code == 200 and ok.json()["tier"] == 2
    too_high = await client.patch(
        f"/accounts/{customer.id}", json={"tier": 4}, headers=_auth(manager)
    )
    assert too_high.status_code == 403


async def test_staff_cannot_edit_or_deactivate_a_manager(client):
    staff = await _make_account("s8@example.com", tier=2)
    manager = await _make_account("m8@example.com", tier=3)
    takeover = await client.patch(
        f"/accounts/{manager.id}", json={"email": "attacker@example.com"}, headers=_auth(staff)
    )
    assert takeover.status_code == 403
    assert (await client.delete(f"/accounts/{manager.id}", headers=_auth(staff))).status_code == 403


async def test_staff_can_still_edit_customers(client):
    staff = await _make_account("s9@example.com", tier=2)
    customer = await _make_account("c9@example.com", tier=1)
    r = await client.patch(f"/accounts/{customer.id}", json={"name": "Fixed Name"}, headers=_auth(staff))
    assert r.status_code == 200 and r.json()["name"] == "Fixed Name"
