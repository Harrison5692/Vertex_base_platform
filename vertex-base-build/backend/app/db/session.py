"""
Async database engine + session dependency.

Uses SQLModel (a thin layer over SQLAlchemy 2.0 async) so table models
double as request/response schemas where it makes sense — less
duplication than maintaining separate SQLAlchemy models and Pydantic
schemas for every table.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a scoped async DB session per request."""
    async with SQLModelAsyncSession(engine) as session:
        yield session
