"""
Single entry point for writing to the audit trail. Every endpoint
that creates/updates/deletes a sensitive record calls this instead
of constructing an AuditLog row inline — keeps the "what counts as
old/new values" logic in one place instead of duplicated per-router.

old_values/new_values are JSON-serialized model dumps, kept simple
and portable rather than a structured diff — a human (or a script)
reading the raw row can always reconstruct exactly what changed.
"""

import json
from datetime import datetime

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.audit_log import AuditLog


async def log_audit(
    session: AsyncSession,
    *,
    table_name: str,
    record_id: int,
    action: str,
    changed_by: int | None,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> None:
    entry = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        changed_by=changed_by,
        old_values=json.dumps(old_values, default=str) if old_values is not None else None,
        new_values=json.dumps(new_values, default=str) if new_values is not None else None,
        created_at=datetime.utcnow(),
    )
    session.add(entry)
    # Deliberately no commit here — caller commits alongside the
    # actual data change so both succeed or fail together in one
    # transaction, rather than risking a logged change that didn't
    # actually happen (or vice versa).
