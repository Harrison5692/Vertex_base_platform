"""
Shared test setup.

Integration tests run against a SEPARATE database — whatever
DATABASE_URL points at, with "_test" appended to the database name
(vertex_base -> vertex_base_test). Your real dev data is never
touched. The test database is created if missing, migrated to head
with the real Alembic migrations (so migrations get tested too), and
every table is wiped before each test.

Run from backend/ (or inside the container):
    docker compose exec backend pytest -q
"""

import os

# Must happen before anything imports app.core.config — Settings reads
# DATABASE_URL once at import time, and env vars beat the .env file.
from app.core.config import Settings  # noqa: E402  (Settings only, not the instance)

_base_url = os.environ.get("DATABASE_URL") or Settings().database_url
_prefix, _, _db_name = _base_url.rpartition("/")
if not _db_name.endswith("_test"):
    _db_name = f"{_db_name}_test"
TEST_DATABASE_URL = f"{_prefix}/{_db_name}"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DEBUG"] = "false"
os.environ.pop("STRIPE_SECRET_KEY", None)  # tests never hit real Stripe

import asyncio  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import asyncpg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

import app.db.session as db_session  # noqa: E402
from app.core.config import settings  # noqa: E402

# NullPool: pytest-asyncio gives each test its own event loop, and a
# pooled asyncpg connection can't be reused across loops.
db_session.engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
settings.database_url = TEST_DATABASE_URL
settings.stripe_secret_key = None


def _asyncpg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _ensure_test_db() -> None:
    admin_dsn = _asyncpg_dsn(f"{_prefix}/postgres")
    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", _db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{_db_name}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
def _migrated_test_db():
    asyncio.run(_ensure_test_db())
    backend_dir = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        check=True,
        capture_output=True,
    )


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(_migrated_test_db):
    async with db_session.engine.begin() as conn:
        tables = (
            await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                    "AND tablename != 'alembic_version'"
                )
            )
        ).scalars().all()
        if tables:
            await conn.execute(
                text(f"TRUNCATE {', '.join(f'"{t}"' for t in tables)} RESTART IDENTITY CASCADE")
            )
    yield


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
