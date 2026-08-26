"""
Generic file reference — a receipt image, a signed form, a product
photo, whatever a deployment needs attached to some other record.
This table does NOT store file bytes and does NOT integrate any
storage provider — it's a pointer (file_url) to wherever the actual
file lives (S3, Cloudinary, local disk in dev, whatever a given
deployment picks). Deciding on a storage backend is a deployment
concern, not a base-schema concern.

entity_type + entity_id is a loose polymorphic reference ("this file
belongs to transaction #42" or "item #7") rather than a dedicated FK
column per attachable table — the base build doesn't know in advance
every table a future vertical might want to attach files to, and
adding a new FK column here for every new entity type would mean
editing this table every time a vertical gets added. The tradeoff:
entity_type/entity_id is NOT a database-enforced foreign key, so
integrity (does entity_id actually exist) is the application's job,
not Postgres's.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class AttachmentBase(SQLModel):
    entity_type: str = Field(index=True, max_length=50)  # e.g. "transaction", "item", "account"
    entity_id: int = Field(index=True)
    file_name: str = Field(max_length=255)
    file_url: str = Field(max_length=1000)
    content_type: str | None = Field(default=None, max_length=100)


class Attachment(AttachmentBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    uploaded_by: int = Field(foreign_key="account.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class AttachmentCreate(AttachmentBase):
    pass


class AttachmentRead(AttachmentBase):
    id: int
    uploaded_by: int
    created_at: datetime
