"""FastAPI dependency injection utilities."""

from typing import AsyncGenerator

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_tenant_id(
    x_tenant_id: str = Header(..., description="Tenant UUID context header")
) -> str:
    """Enforces fail-closed multi-tenancy by requiring X-Tenant-ID on protected routes."""
    if not x_tenant_id or len(x_tenant_id.strip()) < 8:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-Tenant-ID header (Fail-Closed).",
        )
    return x_tenant_id.strip()
