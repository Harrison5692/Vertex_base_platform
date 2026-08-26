"""
Attachments router — upload metadata only. This endpoint does NOT
handle file bytes; the client uploads the actual file to whatever
storage backend the deployment picked (S3, etc.) and then calls this
endpoint with the resulting URL to create the reference record.
Wiring up an actual upload flow (presigned URLs, direct multipart,
whatever) is a deployment concern for CUSTOMIZING.md, not base-schema
work.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import get_current_account
from app.db.session import get_session
from app.models.account import Account
from app.models.attachment import Attachment, AttachmentCreate, AttachmentRead

router = APIRouter(
    prefix="/attachments", tags=["attachments"], dependencies=[Depends(get_current_account)]
)


@router.get("/{entity_type}/{entity_id}", response_model=list[AttachmentRead])
async def list_attachments(
    entity_type: str,
    entity_id: int,
    session: AsyncSession = Depends(get_session),
):
    """All files attached to a given record, e.g. /attachments/transaction/42."""
    result = await session.exec(
        select(Attachment)
        .where(Attachment.entity_type == entity_type, Attachment.entity_id == entity_id)
        .order_by(Attachment.created_at.desc())
    )
    return result.all()


@router.post("/", response_model=AttachmentRead, status_code=201)
async def create_attachment(
    attachment_in: AttachmentCreate,
    session: AsyncSession = Depends(get_session),
    current: Account = Depends(get_current_account),
):
    """Register a reference to an already-uploaded file."""
    attachment = Attachment.model_validate(attachment_in, update={"uploaded_by": current.id})
    session.add(attachment)
    await session.commit()
    await session.refresh(attachment)
    return attachment


@router.delete("/{attachment_id}", status_code=204)
async def delete_attachment(
    attachment_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Removes the reference record only — does not delete the
    underlying file from storage. Deployments that need that should
    hook file deletion in here based on their storage backend."""
    attachment = await session.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    await session.delete(attachment)
    await session.commit()
