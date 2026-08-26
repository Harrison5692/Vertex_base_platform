"""
Generic in-app notification log — "tell an account something
happened." One row per message: an appointment reminder, a low-stock
alert, a payment received confirmation, a staff mention — whatever a
given deployment needs to surface. Deliberately NOT a delivery
system (no email/SMS/push integration here) — this table is the
record of "what was communicated and has it been seen," which every
vertical needs regardless of which channel(s) actually send it.

read_at is nullable and only set once — this is a log, not a mutable
inbox state machine. A deployment wanting per-channel delivery status
(emailed vs not, push-sent vs not) adds that as its own concern on
top of this base record, not by editing this table's meaning.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class NotificationBase(SQLModel):
    account_id: int = Field(foreign_key="account.id", index=True)
    message: str = Field(max_length=1000)
    link: str | None = Field(default=None, max_length=500)


class Notification(NotificationBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_by: int | None = Field(default=None, foreign_key="account.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    read_at: datetime | None = Field(default=None)


class NotificationCreate(NotificationBase):
    pass


class NotificationRead(NotificationBase):
    id: int
    created_by: int | None
    created_at: datetime
    read_at: datetime | None
