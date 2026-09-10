"""
Staff-facing refund approval workflow. See models/refund_approval.py
for the design rationale. Requesting is tier-2+ (staff); reviewing
(approve or deny) is tier-3+ (manager) — a different person than
whoever filed the request is the whole point of a review gate.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.transactions import _has_existing_refund, _issue_refund
from app.core.audit import log_audit
from app.core.deps import get_current_account, require_min_tier
from app.db.session import get_session
from app.models.account import Account
from app.models.refund_approval import (
    RefundApproval,
    RefundApprovalCreate,
    RefundApprovalRead,
    RefundApprovalStatus,
    ReviewRefundApprovalRequest,
)
from app.models.transaction import Transaction, TransactionType

REFUND_WINDOW_DAYS = 30

router = APIRouter(prefix="/refund-approvals", tags=["refund-approvals"])


@router.post(
    "/",
    response_model=RefundApprovalRead,
    status_code=201,
    dependencies=[Depends(require_min_tier(2))],
)
async def request_refund_approval(
    body: RefundApprovalCreate,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """Staff and above. Logs a request for a manager to review —
    nothing moves (money or stock) until approved. Rejected outright
    if the original transaction is more than 30 days old, or already
    has a pending/approved request against it."""
    original = await session.get(Transaction, body.original_transaction_id)
    if not original:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if original.type != TransactionType.completed:
        raise HTTPException(
            status_code=422, detail="Can only request a refund on a completed sale"
        )
    if await _has_existing_refund(session, original.id):
        raise HTTPException(status_code=409, detail="This transaction has already been refunded")
    if datetime.utcnow() - original.created_at > timedelta(days=REFUND_WINDOW_DAYS):
        raise HTTPException(
            status_code=422,
            detail=f"This sale is outside the {REFUND_WINDOW_DAYS}-day refund window",
        )

    existing_result = await session.exec(
        select(RefundApproval).where(
            RefundApproval.original_transaction_id == original.id,
            RefundApproval.status == RefundApprovalStatus.pending,
        )
    )
    if existing_result.first():
        raise HTTPException(
            status_code=409, detail="A refund request is already pending for this transaction"
        )

    if body.requested_amount is not None and body.requested_amount > (original.total or 0.0):
        raise HTTPException(
            status_code=422, detail="requested_amount can't exceed the original total"
        )

    approval = RefundApproval(
        original_transaction_id=original.id,
        reason=body.reason,
        requested_amount=body.requested_amount,
        requested_by=current.id,
    )
    session.add(approval)
    await session.flush()

    await log_audit(
        session,
        table_name="refund_approval",
        record_id=approval.id,
        action="create",
        changed_by=current.id,
        new_values=approval.model_dump(),
    )
    await session.commit()
    await session.refresh(approval)
    return approval


@router.get(
    "/", response_model=list[RefundApprovalRead], dependencies=[Depends(require_min_tier(2))]
)
async def list_refund_approvals(
    pending_only: bool = False,
    session: AsyncSession = Depends(get_session),
):
    query = select(RefundApproval).order_by(RefundApproval.created_at.desc())
    if pending_only:
        query = query.where(RefundApproval.status == RefundApprovalStatus.pending)
    result = await session.exec(query)
    return result.all()


@router.patch(
    "/{approval_id}/review",
    response_model=RefundApprovalRead,
    dependencies=[Depends(require_min_tier(3))],
)
async def review_refund_approval(
    approval_id: int,
    body: ReviewRefundApprovalRequest,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """Manager and above only. notes is required either way — it's
    the record of why this was approved (proof the item came back
    damaged/unopened/etc) or denied. Terminal once reviewed, same as
    everything else that isn't meant to be re-litigated after the
    fact."""
    approval = await session.get(RefundApproval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Refund request not found")
    if approval.status != RefundApprovalStatus.pending:
        raise HTTPException(
            status_code=409, detail=f"This request is already {approval.status.value}"
        )

    original = await session.get(Transaction, approval.original_transaction_id)
    if not original:
        raise HTTPException(status_code=404, detail="Original transaction no longer exists")

    if body.approve:
        if await _has_existing_refund(session, original.id):
            raise HTTPException(
                status_code=409, detail="This transaction was already refunded another way"
            )
        amount = body.amount or approval.requested_amount or (original.total or 0.0)
        if amount <= 0 or amount > (original.total or 0.0):
            raise HTTPException(
                status_code=422, detail="Refund amount must be > 0 and <= original total"
            )
        refund = await _issue_refund(session, original, amount, body.notes, current.id)
        approval.resulting_transaction_id = refund.id
        approval.status = RefundApprovalStatus.approved
    else:
        approval.status = RefundApprovalStatus.denied

    approval.reviewed_by = current.id
    approval.reviewed_at = datetime.utcnow()
    approval.review_notes = body.notes
    session.add(approval)

    await log_audit(
        session,
        table_name="refund_approval",
        record_id=approval.id,
        action="update",
        changed_by=current.id,
        new_values={
            "status": approval.status,
            "resulting_transaction_id": approval.resulting_transaction_id,
        },
    )
    await session.commit()
    await session.refresh(approval)
    return approval
