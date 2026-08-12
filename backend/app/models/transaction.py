"""
History log — every meaningful business action, tied to the account
it involved and the account that performed it (both reference the
same unified `account` table now — a tier-1 client's own purchase
and the tier-2 staff member who processed it are both just accounts).

Foreign keys are explicitly indexed here: Postgres does NOT auto-index
FK columns, only primary keys and unique constraints, so without this
every join/filter on account_id or created_at would be a full table
scan once there's real data volume.
"""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class TransactionType(str, Enum):
    created = "created"
    updated = "updated"
    completed = "completed"
    cancelled = "cancelled"


class TransactionBase(SQLModel):
    account_id: int = Field(foreign_key="account.id", index=True)
    item_id: int | None = Field(default=None, foreign_key="item.id", index=True)
    type: TransactionType
    notes: str | None = None


class Transaction(TransactionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_by: int = Field(foreign_key="account.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class TransactionCreate(TransactionBase):
    pass


class TransactionRead(TransactionBase):
    id: int
    created_by: int
    created_at: datetime
