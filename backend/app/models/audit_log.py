"""
System-wide audit trail. Every write to a sensitive table should
insert a row here — who changed what, old value vs new, when.
Deliberately has no update/delete endpoints anywhere in the API:
an audit log that can be edited isn't an audit log.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    table_name: str = Field(index=True, max_length=100)
    record_id: int = Field(index=True)
    action: str = Field(max_length=20)  # "create" | "update" | "delete"
    changed_by: int | None = Field(default=None, foreign_key="account.id", index=True)
    old_values: str | None = None  # JSON-serialized snapshot, kept simple/portable
    new_values: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
