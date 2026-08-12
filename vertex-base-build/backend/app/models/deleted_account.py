"""
Archive of deactivated accounts (any tier — client, staff, whoever).
The original row still exists (soft-deleted via is_active=False,
never hard-deleted), this table just makes "who got removed, when,
by whom, and what tier were they" a first-class queryable record
instead of something buried in the generic audit log.

Reinstatement = flip is_active back True on the original account,
then set restored_at here.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class DeletedAccount(SQLModel, table=True):
    __tablename__ = "deleted_account"

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)  # not an enforced FK — the account may itself be gone
    tier_at_deletion: int = Field(index=True)
    name: str | None = Field(default=None, max_length=200)
    email: str = Field(max_length=255)
    deleted_by: int = Field(foreign_key="account.id", index=True)
    deleted_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    restored_at: datetime | None = Field(default=None)
