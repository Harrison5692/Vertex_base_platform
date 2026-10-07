"""
Manager-only (tier 3+) management of promo codes. No delete on
purpose: past orders record the code they used, so a code is retired
by deactivating it (PATCH is_active=false), not by removing the row.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit import log_audit
from app.core.deps import require_min_tier
from app.core.discounts import normalize_code
from app.db.session import get_session
from app.models.account import Account
from app.models.discount_code import (
    DiscountCode,
    DiscountCodeCreate,
    DiscountCodeRead,
    DiscountCodeUpdate,
    DiscountKind,
)

router = APIRouter(prefix="/discount-codes", tags=["discount-codes"])


def _check_value(kind: DiscountKind, value: float) -> None:
    if kind == DiscountKind.percent and value > 100:
        raise HTTPException(status_code=422, detail="A percent discount can't be more than 100")


@router.get("/", response_model=list[DiscountCodeRead])
async def list_codes(
    session: AsyncSession = Depends(get_session),
    _: Account = Depends(require_min_tier(3)),
):
    result = await session.exec(select(DiscountCode).order_by(DiscountCode.created_at.desc()))
    return result.all()


@router.post("/", response_model=DiscountCodeRead, status_code=201)
async def create_code(
    body: DiscountCodeCreate,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(require_min_tier(3)),
):
    code = normalize_code(body.code)
    if not code:
        raise HTTPException(status_code=422, detail="Enter a code")
    if not code.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(
            status_code=422, detail="Codes can only use letters, numbers, - and _"
        )
    _check_value(body.kind, body.value)
    existing = await session.exec(select(DiscountCode).where(DiscountCode.code == code))
    if existing.first():
        raise HTTPException(status_code=409, detail=f"{code} already exists")

    dc = DiscountCode.model_validate(body, update={"code": code, "created_by": current.id})
    session.add(dc)
    await session.flush()
    await log_audit(
        session,
        table_name="discount_code",
        record_id=dc.id,
        action="create",
        changed_by=current.id,
        new_values=dc.model_dump(),
    )
    await session.commit()
    await session.refresh(dc)
    return dc


@router.patch("/{code_id}", response_model=DiscountCodeRead)
async def update_code(
    code_id: int,
    body: DiscountCodeUpdate,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(require_min_tier(3)),
):
    dc = await session.get(DiscountCode, code_id)
    if not dc:
        raise HTTPException(status_code=404, detail="Discount code not found")
    changes = body.model_dump(exclude_unset=True)
    if "value" in changes:
        _check_value(dc.kind, changes["value"])
    old_values = {k: getattr(dc, k) for k in changes}
    for key, value in changes.items():
        setattr(dc, key, value)
    session.add(dc)
    await log_audit(
        session,
        table_name="discount_code",
        record_id=dc.id,
        action="update",
        changed_by=current.id,
        old_values=old_values,
        new_values=changes,
    )
    await session.commit()
    await session.refresh(dc)
    return dc
