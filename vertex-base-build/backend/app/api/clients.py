from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_session
from app.models.client import Client, ClientCreate, ClientRead, ClientUpdate
from app.models.deleted_account import DeletedAccount, EntityType
from app.models.user import User

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(get_current_user)])


@router.get("/", response_model=list[ClientRead])
async def list_clients(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Client).where(Client.is_active == True))  # noqa: E712
    return result.all()


@router.post("/", response_model=ClientRead, status_code=201)
async def create_client(client_in: ClientCreate, session: AsyncSession = Depends(get_session)):
    existing = await session.exec(select(Client).where(Client.email == client_in.email))
    if existing.first():
        raise HTTPException(status_code=409, detail="A client with this email already exists")

    client = Client.model_validate(client_in)
    session.add(client)
    await session.commit()
    await session.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientRead)
async def get_client(client_id: int, session: AsyncSession = Depends(get_session)):
    client = await session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientRead)
async def update_client(
    client_id: int, client_in: ClientUpdate, session: AsyncSession = Depends(get_session)
):
    client = await session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for field, value in client_in.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    session.add(client)
    await session.commit()
    await session.refresh(client)
    return client


@router.delete("/{client_id}", status_code=204)
async def deactivate_client(
    client_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Soft delete — sets is_active False, never removes the row.
    Also logs an archive entry so the deletion is easy to find and
    reverse later, without digging through the generic audit log."""
    client = await session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.is_active = False
    session.add(client)

    archive_entry = DeletedAccount(
        entity_type=EntityType.client,
        entity_id=client.id,
        name=client.name,
        email=client.email,
        deleted_by=current_user.id,
    )
    session.add(archive_entry)
    await session.commit()


@router.post("/{client_id}/reinstate", response_model=ClientRead)
async def reinstate_client(
    client_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Reverses a deactivation — reactivates the client and marks
    the most recent archive entry as restored."""
    client = await session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.is_active = True
    session.add(client)

    result = await session.exec(
        select(DeletedAccount)
        .where(
            DeletedAccount.entity_type == EntityType.client,
            DeletedAccount.entity_id == client_id,
            DeletedAccount.restored_at.is_(None),
        )
        .order_by(DeletedAccount.deleted_at.desc())
    )
    archive_entry = result.first()
    if archive_entry:
        from datetime import datetime

        archive_entry.restored_at = datetime.utcnow()
        session.add(archive_entry)

    await session.commit()
    await session.refresh(client)
    return client
