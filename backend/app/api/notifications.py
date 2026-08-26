"""
Notifications router — self-service only. An account manages its
own notifications (list, mark read); creating notifications on
someone else's behalf is a staff+ action, since it's how the system
tells an account something happened, not something accounts do to
each other freely.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import get_current_account, require_min_tier
from app.db.session import get_session
from app.models.account import Account
from app.models.notification import Notification, NotificationCreate, NotificationRead

router = APIRouter(
    prefix="/notifications", tags=["notifications"], dependencies=[Depends(get_current_account)]
)


@router.get("/", response_model=list[NotificationRead])
async def list_my_notifications(
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """The current account's own notifications, newest first."""
    result = await session.exec(
        select(Notification)
        .where(Notification.account_id == current.id)
        .order_by(Notification.created_at.desc())
    )
    return result.all()


@router.post(
    "/", response_model=NotificationRead, status_code=201,
    dependencies=[Depends(require_min_tier(2))],
)
async def create_notification(
    notif_in: NotificationCreate,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """Staff and above only — send a notification to an account."""
    target = await session.get(Account, notif_in.account_id)
    if not target:
        raise HTTPException(status_code=404, detail="Account not found")

    notification = Notification.model_validate(notif_in, update={"created_by": current.id})
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    return notification


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_read(
    notification_id: int,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """Mark one of the current account's own notifications as read."""
    notification = await session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.account_id != current.id:
        raise HTTPException(status_code=403, detail="Can only mark your own notifications read")

    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
    return notification
