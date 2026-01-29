import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def _to_asyncpg_dsn(url: str) -> str:
    """
    Convert common Postgres URLs (postgres://, postgresql://) to SQLAlchemy asyncpg DSN.

    SQLAlchemy's async engine expects a driver name, like:
      postgresql+asyncpg://user:pass@host:port/db
    """
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    # Fallback: assume caller already provided something workable.
    return url


# Lazily created module-level singletons
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


# PUBLIC_INTERFACE
def get_engine() -> AsyncEngine:
    """Get (or create) the global async SQLAlchemy engine configured via env vars."""
    global _engine

    if _engine is not None:
        return _engine

    # These env vars are provided by the "database" container integration.
    # Request these from the orchestrator if missing in your environment:
    #   POSTGRES_URL, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_PORT
    postgres_url = os.getenv("POSTGRES_URL")
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD")
    postgres_db = os.getenv("POSTGRES_DB")

    if postgres_url:
        dsn = _to_asyncpg_dsn(postgres_url)
    else:
        # Conservative fallback; many platforms provide HOST in POSTGRES_URL, but if not,
        # try composing from the remaining env vars.
        if not (postgres_user and postgres_password and postgres_db):
            raise RuntimeError(
                "Database configuration missing. Provide POSTGRES_URL or "
                "POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB env vars."
            )
        # Default to localhost; deployments should set POSTGRES_URL.
        postgres_port = os.getenv("POSTGRES_PORT", "5432")
        dsn = f"postgresql+asyncpg://{postgres_user}:{postgres_password}@localhost:{postgres_port}/{postgres_db}"

    _engine = create_async_engine(
        dsn,
        pool_pre_ping=True,
        future=True,
    )
    return _engine


# PUBLIC_INTERFACE
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Get (or create) the global async sessionmaker."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _sessionmaker


# PUBLIC_INTERFACE
@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an AsyncSession."""
    session_maker = get_sessionmaker()
    async with session_maker() as session:
        yield session


# PUBLIC_INTERFACE
async def init_db() -> None:
    """
    Initialize database objects required by the app.

    We create minimal tables using SQLAlchemy DDL so the app can run without migrations.
    In production, migrations are recommended (Alembic).
    """
    from src.api.models import Base  # local import to avoid circular deps

    engine = get_engine()
    async with engine.begin() as conn:
        # Helpful extension for UUID generation (optional); safe if not available.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
        await conn.run_sync(Base.metadata.create_all)
