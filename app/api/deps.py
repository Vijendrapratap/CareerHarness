"""FastAPI dependency injection utilities with RLS and session authentication."""

from typing import AsyncGenerator, Optional

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token
from app.core.config import settings
from app.core.database import async_session_factory
from app.domain.models import User

security_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_token_from_request(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    session_token: Optional[str] = Cookie(default=None),
) -> Optional[str]:
    """Extracts JWT token from Bearer header or HttpOnly session cookie."""
    if auth_header and auth_header.credentials:
        return auth_header.credentials
    if session_token:
        return session_token
    return None


async def get_current_user(
    token: Optional[str] = Depends(get_token_from_request),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Authenticates request and returns the current user, or raises 401."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired credentials: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload.",
        )

    user_stmt = select(User).where(User.id == user_id, User.is_active.is_(True))
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    # Set Postgres session setting for RLS (Phase 0 Directive)
    if "postgresql" in settings.DATABASE_URL:
        await session.execute(
            text("SELECT set_tenant_id(:tenant_id)"),
            {"tenant_id": user.tenant_id},
        )

    return user


async def get_tenant_id(
    request: Request,
    x_tenant_id: Optional[str] = Header(default=None, description="Tenant UUID context header"),
    token: Optional[str] = Depends(get_token_from_request),
    session: AsyncSession = Depends(get_db),
) -> str:
    """Enforces fail-closed multi-tenancy. Resolves tenant_id from header or session token."""
    resolved_tenant_id: Optional[str] = None

    if x_tenant_id and len(x_tenant_id.strip()) >= 8:
        resolved_tenant_id = x_tenant_id.strip()
    elif token:
        try:
            payload = decode_access_token(token)
            resolved_tenant_id = payload.get("tenant_id")
        except Exception:
            pass

    if not resolved_tenant_id or len(resolved_tenant_id) < 8:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-Tenant-ID header or session token (Fail-Closed).",
        )

    # Set Postgres session setting for RLS (Phase 0 Directive)
    if "postgresql" in settings.DATABASE_URL:
        await session.execute(
            text("SELECT set_tenant_id(:tenant_id)"),
            {"tenant_id": resolved_tenant_id},
        )

    return resolved_tenant_id
