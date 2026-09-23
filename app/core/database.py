"""Database engine, session management, and RLS isolation enforcement."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.domain.models import Base

# Engine configuration
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    future=True,
    # SQLite (dev) allows one writer: wait up to 30s for the lock instead of failing after 5s.
    connect_args={"timeout": 30} if settings.DATABASE_URL.startswith("sqlite") else {},
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initializes schema and tables (for dev/test environments)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_tenant_session(
    tenant_id: Optional[str] = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Provides an AsyncSession scoped to a specific tenant.

    Enforces:
    - IT-02: Row-Level Security (RLS) parameter binding on Postgres.
    - Fail-closed: If tenant_id is provided, sets app.current_tenant_id.
    """
    async with async_session_factory() as session:
        if tenant_id:
            # Set Postgres session setting for RLS
            if "postgresql" in settings.DATABASE_URL:
                await session.execute(
                    text("SET LOCAL app.current_tenant_id = :tenant_id"),
                    {"tenant_id": tenant_id},
                )
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
