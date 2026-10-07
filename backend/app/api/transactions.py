"""
History log — every meaningful action, timestamped and tied to the
account it involved (if any — see guest_label on the model) and the
account that performed it. Read-heavy by design: this is the
audit-friendly record a business (or a regulator) would want to
review, so there's deliberately no update/delete endpoint — history
doesn't get edited after the fact, only appended to (refund/void are
new Transaction rows, not edits of the original).

A transaction is created with its line items in one call — the
client sends item_id/quantity/unit_price pairs, the server computes
subtotal/total and writes both the Transaction header and its
TransactionLine rows atomically.

Access follows the same tier pattern as accounts.py: a tier-1 account
sees only their own transactions, tier-2+ (staff) can see anyone's.
"""

from datetime import datetime
import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit import log_audit
from app.core.client_config import client_config
from app.core.config import settings
from app.core.deps import get_current_account, get_current_account_optional, require_min_tier
from app.core.email import get_email_provider
from app.core.payments import get_payment_provider
from app.core.pricing import PricingError, Totals, compute_totals, validate_destination
from app.core.stock import maybe_notify_low_stock
from app.db.session import get_session
from app.models.account import Account
from app.models.item import Item
from app.models.transaction import (
    FulfillmentStatus,
    PaymentMethod,
    Transaction,
    TransactionCreate,
    TransactionRead,
    TransactionType,
)
from app.models.transaction_line import (
    TransactionLine,
    TransactionLineCreate,
    TransactionLineRead,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])
# No router-level auth dependency — POST / (create_transaction) is
# the one endpoint that must serve BOTH logged-in and guest requests
# (guest checkout), so it uses get_current_account_optional itself.
# Every other endpoint below carries its own explicit
# get_current_account/require_min_tier dependency, so removing the
# blanket router-level requirement doesn't leave any of them open.


class TransactionWithLines(TransactionRead):
    lines: list[TransactionLineRead] = []


class TransactionCreateRequest(TransactionCreate):
    lines: list[TransactionLineCreate]
    # Staff-only override (e.g. a tax-exempt walk-in sale). Ignored for
    # anyone else — customer tax is always computed server-side.
    tax_amount: float | None = PydanticField(default=None, ge=0)


class QuoteLine(BaseModel):
    item_id: int
    quantity: int = PydanticField(default=1, ge=1)
    # Only honored for staff, same as checkout — see _price_lines.
    unit_price: float | None = PydanticField(default=None, ge=0)


class QuoteRequest(BaseModel):
    lines: list[QuoteLine]
    online: bool = True
    shipping_country: str | None = None
    shipping_state: str | None = None
    tax_amount: float | None = PydanticField(default=None, ge=0)


class QuoteResponse(BaseModel):
    subtotal: float
    shipping: float
    tax: float
    total: float
    free_shipping_remaining: float | None


def _is_staff(account: Account | None) -> bool:
    return account is not None and account.tier >= 2


def _price_lines(lines, items_by_id: dict[int, Item], is_staff: bool) -> list[float]:
    """Unit price per line. Staff may set their own (a manual
    discount at the register); everyone else pays the catalog price
    as it is RIGHT NOW — never a client-supplied number, which a
    customer could otherwise just edit to 0.01."""
    prices = []
    for line in lines:
        item = items_by_id[line.item_id]
        if is_staff and line.unit_price is not None:
            prices.append(line.unit_price)
            continue
        if item.price is None or not item.is_active:
            raise HTTPException(status_code=422, detail=f"{item.name} isn't available for purchase")
        prices.append(item.price)
    return prices


def _totals(
    lines, prices: list[float], *, online: bool, state: str | None, tax_override: float | None
) -> Totals:
    subtotal = sum(line.quantity * price for line, price in zip(lines, prices, strict=True))
    return compute_totals(
        subtotal, online=online, state=state, config=client_config, tax_override=tax_override
    )


class RefundRequest(BaseModel):
    amount: float | None = PydanticField(default=None, gt=0)  # None = full refund of the original total
    notes: str | None = None


@router.get(
    "/", response_model=list[TransactionRead], dependencies=[Depends(require_min_tier(2))]
)
async def list_transactions(session: AsyncSession = Depends(get_session)):
    """Staff and above only — every transaction, across every account."""
    result = await session.exec(select(Transaction).order_by(Transaction.created_at.desc()))
    return result.all()


@router.get("/export", dependencies=[Depends(require_min_tier(2))])
async def export_transactions(
    session: AsyncSession = Depends(get_session),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """Staff and above only. CSV export of transaction history —
    every business wants a copy of its own sales data outside the
    system (accounting, taxes, a spreadsheet). Deliberately placed
    BEFORE /{transaction_id} below: a static path must be registered
    ahead of a dynamic one sharing the same prefix, or FastAPI tries
    to parse "export" as a transaction id and 422s before ever
    reaching this route."""
    query = select(Transaction).order_by(Transaction.created_at.asc())
    if start_date:
        query = query.where(Transaction.created_at >= start_date)
    if end_date:
        query = query.where(Transaction.created_at <= end_date)
    result = await session.exec(query)
    transactions = result.all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id", "created_at", "type", "account_id", "guest_label", "payment_method",
            "payment_reference", "subtotal", "shipping_amount", "tax_amount", "total",
            "deposit_amount", "balance_due", "related_transaction_id", "created_by", "notes",
        ]
    )
    for tx in transactions:
        writer.writerow(
            [
                tx.id, tx.created_at.isoformat(), tx.type, tx.account_id, tx.guest_label,
                tx.payment_method, tx.payment_reference, tx.subtotal, tx.shipping_amount,
                tx.tax_amount, tx.total,
                tx.deposit_amount, tx.balance_due, tx.related_transaction_id, tx.created_by,
                tx.notes,
            ]
        )
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


@router.get("/account/{account_id}", response_model=list[TransactionRead])
async def get_account_history(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """A single account's full history — self, or staff and above."""
    if current.tier < 2 and current.id != account_id:
        raise HTTPException(status_code=403, detail="Can only view your own history")

    account = await session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    result = await session.exec(
        select(Transaction)
        .where(Transaction.account_id == account_id)
        .order_by(Transaction.created_at.desc())
    )
    return result.all()


@router.get(
    "/queue", response_model=list[TransactionRead], dependencies=[Depends(require_min_tier(2))]
)
async def get_fulfillment_queue(session: AsyncSession = Depends(get_session)):
    """Staff and above only. Active online orders awaiting fulfillment
    (pending or processing) — oldest first, so staff naturally work
    through it FIFO. Placed before /{transaction_id} for the same
    static-vs-dynamic-route reason as /export above."""
    result = await session.exec(
        select(Transaction)
        .where(
            Transaction.fulfillment_status.in_(
                [FulfillmentStatus.pending, FulfillmentStatus.processing]
            )
        )
        .order_by(Transaction.created_at.asc())
    )
    return result.all()


@router.post("/quote", response_model=QuoteResponse)
async def quote_transaction(
    body: QuoteRequest,
    session: AsyncSession = Depends(get_session),
    current_account: Account | None = Depends(get_current_account_optional),
):
    """Public — what checkout WILL charge for this cart and
    destination, computed by the exact same code path as
    create_transaction. The cart page displays this instead of doing
    its own math. Read-only, no locking: the real numbers are
    recomputed at checkout regardless."""
    if not body.lines:
        return QuoteResponse(subtotal=0, shipping=0, tax=0, total=0, free_shipping_remaining=None)
    is_staff = _is_staff(current_account)
    state = None
    if body.online and body.shipping_state:
        try:
            _, state = validate_destination(
                body.shipping_country or "US", body.shipping_state, client_config
            )
        except PricingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    item_ids = {line.item_id for line in body.lines}
    result = await session.exec(select(Item).where(Item.id.in_(item_ids)))
    items_by_id = {item.id: item for item in result.all()}
    missing_ids = item_ids - set(items_by_id)
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Item id(s) not found: {sorted(missing_ids)}")

    prices = _price_lines(body.lines, items_by_id, is_staff)
    totals = _totals(
        body.lines,
        prices,
        online=body.online,
        state=state,
        tax_override=body.tax_amount if is_staff else None,
    )
    return QuoteResponse(**totals.__dict__)


@router.get("/{transaction_id}", response_model=TransactionWithLines)
async def get_transaction(
    transaction_id: int,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """A single transaction with its line items — self, or staff and above."""
    transaction = await session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if current.tier < 2 and current.id != transaction.account_id:
        raise HTTPException(status_code=403, detail="Can only view your own transactions")

    result = await session.exec(
        select(TransactionLine).where(TransactionLine.transaction_id == transaction_id)
    )
    lines = result.all()
    return TransactionWithLines(**transaction.model_dump(), lines=lines)


@router.post("/", response_model=TransactionWithLines, status_code=201)
async def create_transaction(
    tx_in: TransactionCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_account: Account | None = Depends(get_current_account_optional),
):
    """account_id is optional — a guest/walk-in sale passes null and
    relies on guest_label instead. Requires at least one line item;
    subtotal/total are computed server-side from the lines, never
    trusted from the client.

    Guest checkout: current_account is None whenever no Authorization
    header was sent at all (see get_current_account_optional) — a
    logged-in customer or staff member still authenticates normally.
    An online order (has a shipping address) placed with no account
    at all requires guest_email, since that's the only way to send a
    receipt; a staff walk-in POS sale needs neither."""
    is_staff = _is_staff(current_account)
    if not is_staff:
        # A customer (logged in or guest) can only ever place their own
        # completed online order: they can't attach it to someone
        # else's account, record a "refund", or ring up a walk-in sale
        # with no shipping and no payment. Staff keep full control.
        tx_in.account_id = current_account.id if current_account else None
        if tx_in.type != TransactionType.completed:
            raise HTTPException(status_code=403, detail="Customers can only place orders")
        if not tx_in.shipping_line1:
            raise HTTPException(status_code=422, detail="A shipping address is required")
        # With real card charging configured, a customer order must
        # actually be paid by card — otherwise picking "cash" would
        # create an unpaid order that goes straight into fulfillment.
        if settings.stripe_secret_key and not (
            tx_in.payment_method == PaymentMethod.card and tx_in.stripe_payment_method_id
        ):
            raise HTTPException(status_code=422, detail="Card payment is required")

    account = None
    if tx_in.account_id is not None:
        account = await session.get(Account, tx_in.account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

    is_online_order = bool(tx_in.shipping_line1)
    if is_online_order:
        try:
            tx_in.shipping_country, tx_in.shipping_state = validate_destination(
                tx_in.shipping_country, tx_in.shipping_state, client_config
            )
        except PricingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if is_online_order and account is None and current_account is None and not tx_in.guest_email:
        raise HTTPException(
            status_code=422, detail="An email is required to check out without an account"
        )

    if not tx_in.lines:
        raise HTTPException(status_code=422, detail="A transaction needs at least one line item")

    # Validate every referenced item exists BEFORE creating anything —
    # letting a bad item_id reach the database insert means a raw FK
    # violation (500) instead of a clean, actionable error. Locked
    # with FOR UPDATE so two concurrent checkouts against the same
    # low-stock item can't both read "3 left" and both succeed — the
    # second one blocks here until the first commits or rolls back,
    # then re-reads the updated count.
    item_ids = {line.item_id for line in tx_in.lines}
    result = await session.exec(select(Item).where(Item.id.in_(item_ids)).with_for_update())
    items_by_id = {item.id: item for item in result.all()}
    missing_ids = item_ids - set(items_by_id)
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Item id(s) not found: {sorted(missing_ids)}",
        )

    # Stock check — only for items that actually track stock (retail).
    # A service/catering item that leaves stock_quantity null is
    # exempt by design, same as everywhere else stock is touched.
    requested_qty: dict[int, int] = {}
    for line in tx_in.lines:
        requested_qty[line.item_id] = requested_qty.get(line.item_id, 0) + line.quantity

    insufficient = []
    for item_id, qty in requested_qty.items():
        item = items_by_id[item_id]
        if item.stock_quantity is not None and qty > item.stock_quantity:
            insufficient.append(f"{item.name} (requested {qty}, {item.stock_quantity} in stock)")
    if insufficient:
        raise HTTPException(status_code=409, detail=f"Not enough stock: {'; '.join(insufficient)}")

    prices = _price_lines(tx_in.lines, items_by_id, is_staff)
    totals = _totals(
        tx_in.lines,
        prices,
        online=is_online_order,
        state=tx_in.shipping_state,
        tax_override=tx_in.tax_amount if is_staff else None,
    )
    total = totals.total

    # If this is a real card charge (the storefront's Stripe Elements
    # form supplied a token), attempt it now, against the
    # server-computed total — never a client-supplied amount. A
    # staff-run POS sale (payment_method=card but no token, meaning
    # the card was swiped on a separate physical terminal) skips this
    # entirely and behaves exactly as before. Deliberately BEFORE any
    # row is written: a declined card means nothing gets created, not
    # a transaction row that then has to be cleaned up.
    payment_reference = None
    if tx_in.payment_method == PaymentMethod.card and tx_in.stripe_payment_method_id:
        provider = get_payment_provider()
        result = await provider.charge(
            amount=total,
            currency="usd",
            metadata={"payment_method_id": tx_in.stripe_payment_method_id},
        )
        if not result.success:
            raise HTTPException(status_code=402, detail=result.message or "Payment failed.")
        payment_reference = result.reference

    tx_data = tx_in.model_dump(exclude={"lines", "tax_amount", "stripe_payment_method_id"})
    transaction = Transaction.model_validate(
        tx_data,
        update={
            "created_by": current_account.id if current_account else None,
            "subtotal": totals.subtotal,
            "shipping_amount": totals.shipping if is_online_order else None,
            "tax_amount": totals.tax,
            "total": totals.total,
            "payment_reference": payment_reference,
            # An online order (has a shipping address) enters the
            # fulfillment pipeline at "pending"; a staff walk-in POS
            # sale (no shipping address) has nothing to fulfill and
            # stays null, same as it always has.
            "fulfillment_status": (
                FulfillmentStatus.pending
                if tx_in.type == TransactionType.completed and tx_in.shipping_line1
                else None
            ),
        },
    )
    session.add(transaction)
    await session.flush()  # assigns transaction.id without committing/expiring attributes

    lines = []
    for line_in, unit_price in zip(tx_in.lines, prices, strict=True):
        line = TransactionLine(
            transaction_id=transaction.id,
            item_id=line_in.item_id,
            quantity=line_in.quantity,
            unit_price=unit_price,
            line_total=round(line_in.quantity * unit_price, 2),
        )
        session.add(line)
        lines.append(line)
    await session.flush()  # assigns each line.id, still no commit/expire

    # Decrement stock now that the sale is confirmed — same
    # session/transaction as everything else here, so any failure
    # below rolls this back too instead of leaving stock out of sync
    # with what was actually sold.
    for item_id, qty in requested_qty.items():
        item = items_by_id[item_id]
        if item.stock_quantity is None:
            continue
        previous_stock = item.stock_quantity
        item.stock_quantity -= qty
        session.add(item)
        await maybe_notify_low_stock(
            session,
            item,
            previous_stock=previous_stock,
            current_account_id=current_account.id if current_account else None,
        )

    await log_audit(
        session,
        table_name="transaction",
        record_id=transaction.id,
        action="create",
        changed_by=current_account.id if current_account else None,
        new_values={**transaction.model_dump(), "lines": [l.model_dump() for l in lines]},
    )
    # Captured BEFORE commit: commit expires every loaded object, and
    # reading item.name afterwards would trigger a lazy load outside
    # the async context (MissingGreenlet) — crashing the response
    # AFTER the order was saved and the card charged.
    item_names = {item_id: item.name for item_id, item in items_by_id.items()}
    receipt_email = account.email if account is not None else tx_in.guest_email
    await session.commit()
    await session.refresh(transaction)
    for line in lines:
        await session.refresh(line)

    # Order confirmation — to the account's email if there is one,
    # otherwise to guest_email for a guest checkout. A staff walk-in
    # POS sale (guest_label, no account, no guest_email) gets neither,
    # same as before.
    if receipt_email:
        provider = get_email_provider()
        line_summary = "\n".join(
            f"  {line.quantity} x {item_names[line.item_id]} — ${line.line_total:.2f}"
            for line in lines
        )
        body = (
            f"Thanks for your order — transaction #{transaction.id}\n\n"
            f"{line_summary}\n\n"
            f"Subtotal: ${transaction.subtotal:.2f}\n"
            + (
                f"Shipping: ${transaction.shipping_amount:.2f}\n"
                if transaction.shipping_amount is not None
                else ""
            )
            + f"Tax: ${transaction.tax_amount:.2f}\n"
            f"Total: ${transaction.total:.2f}"
        )
        await provider.send(to=receipt_email, subject="Order confirmation", body=body)

    return TransactionWithLines(**transaction.model_dump(), lines=lines)


async def _has_existing_refund(session: AsyncSession, transaction_id: int) -> bool:
    existing = await session.exec(
        select(Transaction).where(
            Transaction.related_transaction_id == transaction_id,
            Transaction.type == TransactionType.refunded,
        )
    )
    return existing.first() is not None


async def _issue_refund(
    session: AsyncSession,
    original: Transaction,
    amount: float,
    notes: str | None,
    performed_by: int,
) -> Transaction:
    """Attempts the actual money movement FIRST (if the original has a
    payment_reference, e.g. a Stripe charge) and only creates the
    refund Transaction row if that succeeds — same "money moves
    before rows get written" principle as checkout, so the books
    never claim a refund happened when the charge didn't actually
    reverse. Shared by the manager-only direct refund endpoint,
    refund-approval review (see api/refund_approvals.py), and order
    cancellation below.

    Never touches stock — restocking is always a separate, explicit
    decision: through the returns system for something a customer
    physically sends back (needs inspection first), or directly in
    update_fulfillment_status for an order cancelled before it ever
    shipped (nothing to inspect, it never left)."""
    if original.payment_reference:
        provider = get_payment_provider()
        result = await provider.refund(original.payment_reference, amount)
        if not result.success:
            raise HTTPException(status_code=402, detail=result.message or "Refund failed.")

    refund = Transaction(
        account_id=original.account_id,
        guest_label=original.guest_label,
        guest_email=original.guest_email,
        type=TransactionType.refunded,
        payment_method=original.payment_method,
        notes=notes,
        related_transaction_id=original.id,
        subtotal=-amount,
        tax_amount=0.0,
        total=-amount,
        created_by=performed_by,
    )
    session.add(refund)
    await session.flush()  # assigns refund.id without committing/expiring attributes
    return refund


@router.post("/{transaction_id}/refund", response_model=TransactionWithLines, status_code=201)
async def refund_transaction(
    transaction_id: int,
    body: RefundRequest,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(require_min_tier(3)),
):
    """Manager and above only (tier 3+) — a DIRECT override that
    bypasses the normal review process. Day to day, tier-2 staff use
    api/refund_approvals.py instead: log a request, a manager reviews
    it, and approval calls this exact same underlying logic. This
    endpoint exists for a manager who's already satisfied a refund is
    warranted and doesn't need a separate approval step for their own
    decision — refunds still aren't a button any staff member can
    click instantly, they're just gated by tier instead of by a
    review record for someone at this level.

    Creates a NEW transaction of type 'refunded' linked back to the
    original via related_transaction_id — the original row is never
    edited, per the append-only history rule. Defaults to a full
    refund of the original's total; pass `amount` for a partial
    refund. Line items aren't itemized on the refund by default (a
    partial refund isn't necessarily tied to specific items) — see
    api/returns.py for that."""
    original = await session.get(Transaction, transaction_id)
    if not original:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if original.type in (TransactionType.refunded, TransactionType.voided):
        raise HTTPException(status_code=409, detail="Cannot refund a refund/void transaction itself")
    if await _has_existing_refund(session, transaction_id):
        raise HTTPException(status_code=409, detail="Transaction has already been refunded")

    refund_amount = body.amount if body.amount is not None else (original.total or 0.0)
    if refund_amount <= 0 or refund_amount > (original.total or 0.0):
        raise HTTPException(status_code=422, detail="Refund amount must be > 0 and <= original total")

    refund = await _issue_refund(session, original, refund_amount, body.notes, current.id)

    await log_audit(
        session,
        table_name="transaction",
        record_id=refund.id,
        action="create",
        changed_by=current.id,
        new_values={**refund.model_dump(), "refunds_transaction_id": original.id},
    )
    await session.commit()
    await session.refresh(refund)

    return TransactionWithLines(**refund.model_dump(), lines=[])


class FulfillmentUpdateRequest(BaseModel):
    status: FulfillmentStatus
    # Only meaningful when status is "shipped" — stored on the
    # transaction and included in the shipped-notification email.
    tracking_number: str | None = None


@router.patch(
    "/{transaction_id}/fulfillment",
    response_model=TransactionRead,
    dependencies=[Depends(require_min_tier(2))],
)
async def update_fulfillment_status(
    transaction_id: int,
    body: FulfillmentUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """Staff and above only. Moves an order through
    pending -> processing -> shipped -> delivered, or sideways to
    cancelled. Marking shipped optionally records a tracking_number
    and emails the customer a shipped notification. Cancelling
    restocks every line item and refunds the full amount automatically
    (see below) — delivered/cancelled are both terminal after that;
    this endpoint refuses further changes once there (the
    append-only-history approach used elsewhere doesn't apply here
    since this is a status field, not a financial event, but "no more
    changes once done" is still the safer default than silently
    allowing it)."""
    transaction = await session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if transaction.fulfillment_status is None:
        raise HTTPException(
            status_code=409,
            detail="This transaction has no fulfillment pipeline — it isn't an online order",
        )
    if transaction.fulfillment_status in (FulfillmentStatus.delivered, FulfillmentStatus.cancelled):
        raise HTTPException(
            status_code=409,
            detail=f"Order is already {transaction.fulfillment_status.value} — that's final",
        )

    old_status = transaction.fulfillment_status

    if body.status == FulfillmentStatus.cancelled:
        # Cancelling before shipment means the items never actually
        # left — restock them automatically, unlike a post-delivery
        # return (which needs physical inspection first, so it goes
        # through returns.py / refund_approvals.py instead). Also
        # refund the full amount: as far as the customer's concerned,
        # the order never happened.
        lines_result = await session.exec(
            select(TransactionLine).where(TransactionLine.transaction_id == transaction_id)
        )
        order_lines = lines_result.all()
        order_item_ids = {order_line.item_id for order_line in order_lines}
        items_result = await session.exec(
            select(Item).where(Item.id.in_(order_item_ids)).with_for_update()
        )
        order_items_by_id = {order_item.id: order_item for order_item in items_result.all()}
        for order_line in order_lines:
            order_item = order_items_by_id.get(order_line.item_id)
            if order_item and order_item.stock_quantity is not None:
                order_item.stock_quantity += order_line.quantity
                session.add(order_item)

        if not await _has_existing_refund(session, transaction_id) and (transaction.total or 0) > 0:
            await _issue_refund(
                session,
                transaction,
                transaction.total,
                "Order cancelled before shipment",
                current.id,
            )

    if body.status == FulfillmentStatus.shipped:
        if body.tracking_number:
            transaction.tracking_number = body.tracking_number

        if transaction.account_id:
            shipped_account = await session.get(Account, transaction.account_id)
            receipt_email = shipped_account.email if shipped_account else None
        else:
            receipt_email = transaction.guest_email

        if receipt_email:
            # Itemized the same way the order-confirmation email is —
            # a fresh lookup here since this endpoint doesn't already
            # have the lines/items in scope (unlike create_transaction).
            lines_result = await session.exec(
                select(TransactionLine).where(TransactionLine.transaction_id == transaction_id)
            )
            shipped_lines = lines_result.all()
            shipped_item_ids = {line.item_id for line in shipped_lines}
            shipped_items_result = await session.exec(
                select(Item).where(Item.id.in_(shipped_item_ids))
            )
            shipped_items_by_id = {i.id: i for i in shipped_items_result.all()}
            line_summary = "\n".join(
                f"  {line.quantity} x {shipped_items_by_id[line.item_id].name}"
                for line in shipped_lines
            )
            tracking_line = (
                f"Tracking number: {transaction.tracking_number}\n\n"
                if transaction.tracking_number
                else ""
            )
            body_text = (
                f"Your order #{transaction.id} has shipped!\n\n"
                f"{tracking_line}"
                f"{line_summary}\n\n"
                f"Total: ${transaction.total:.2f}"
            )
            provider = get_email_provider()
            await provider.send(
                to=receipt_email, subject="Your order has shipped", body=body_text
            )

    transaction.fulfillment_status = body.status
    session.add(transaction)

    await log_audit(
        session,
        table_name="transaction",
        record_id=transaction.id,
        action="update",
        changed_by=current.id,
        old_values={"fulfillment_status": old_status},
        new_values={"fulfillment_status": body.status},
    )
    await session.commit()
    await session.refresh(transaction)
    return transaction
