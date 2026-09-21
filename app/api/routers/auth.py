"""Authentication API Router (Phase 0, Email/Password + Argon2id + Sessions).

Enforces:
- No social login
- Argon2id password hashing
- Session cookies (HttpOnly, Secure in prod)
- Magic link password reset
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.auth import (
    create_access_token,
    create_magic_link_token,
    hash_password,
    verify_magic_link_token,
    verify_password,
)
from app.core.config import settings
from app.domain.models import Tenant, User

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    name: str = Field(..., min_length=2, max_length=255, description="Candidate name")
    plan: str = Field(default="pro", description="'free' or 'pro'")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerifyRequest(BaseModel):
    token: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    tenant_id: str
    is_active: bool


class TenantInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    plan: str
    trusted_mode: bool


class AuthResponse(BaseModel):
    user: UserResponse
    tenant: TenantInfo
    access_token: str
    token_type: str = "bearer"


def set_session_cookie(response: Response, token: str) -> None:
    """Sets secure HttpOnly session cookie on response."""
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    req: SignupRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    """Registers a new user and tenant using Argon2id password hashing."""
    # 1. Check if email already exists
    existing_stmt = select(User).where(User.email == req.email.lower().strip())
    existing_user = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # 2. Create Tenant
    tenant = Tenant(
        name=req.name.strip(),
        plan=req.plan.lower().strip(),
        trusted_mode=False,
        is_active=True,
    )
    session.add(tenant)
    await session.flush()  # Populates tenant.id

    # 3. Hash password using Argon2id and create User
    hashed_pwd = hash_password(req.password)
    user = User(
        email=req.email.lower().strip(),
        password_hash=hashed_pwd,
        tenant_id=tenant.id,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(tenant)
    await session.refresh(user)

    # 4. Generate signed session token
    token = create_access_token(
        data={"sub": user.id, "tenant_id": tenant.id, "email": user.email}
    )
    set_session_cookie(response, token)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        tenant=TenantInfo.model_validate(tenant),
        access_token=token,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    req: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    """Authenticates user with email and Argon2id password, setting HttpOnly session cookie."""
    stmt = select(User).where(User.email == req.email.lower().strip())
    user = (await session.execute(stmt)).scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    # Fetch associated tenant
    tenant_stmt = select(Tenant).where(Tenant.id == user.tenant_id)
    tenant = (await session.execute(tenant_stmt)).scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User tenant mapping missing.",
        )

    token = create_access_token(
        data={"sub": user.id, "tenant_id": tenant.id, "email": user.email}
    )
    set_session_cookie(response, token)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        tenant=TenantInfo.model_validate(tenant),
        access_token=token,
    )


@router.post("/logout")
async def logout(response: Response):
    """Clears session cookie."""
    response.delete_cookie(key="session_token")
    return {"status": "logged_out"}


@router.get("/me", response_model=AuthResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Returns currently authenticated user profile and tenant details."""
    tenant_stmt = select(Tenant).where(Tenant.id == current_user.tenant_id)
    tenant = (await session.execute(tenant_stmt)).scalar_one_or_none()
    token = create_access_token(
        data={"sub": current_user.id, "tenant_id": current_user.tenant_id, "email": current_user.email}
    )

    return AuthResponse(
        user=UserResponse.model_validate(current_user),
        tenant=TenantInfo.model_validate(tenant),
        access_token=token,
    )


@router.post("/magic-link")
async def request_magic_link(
    req: MagicLinkRequest,
    session: AsyncSession = Depends(get_db),
):
    """Generates a secure password reset / login magic link."""
    stmt = select(User).where(User.email == req.email.lower().strip())
    user = (await session.execute(stmt)).scalar_one_or_none()

    if not user:
        # Don't leak whether email exists
        return {"status": "sent", "detail": "If this email is registered, a magic link has been sent."}

    token = create_magic_link_token(user.email)
    return {
        "status": "sent",
        "detail": "Magic link generated.",
        "magic_link": f"/auth/verify?token={token}",
        "token": token,
    }


@router.post("/magic-link/verify", response_model=AuthResponse)
async def verify_magic_link(
    req: MagicLinkVerifyRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    """Verifies magic link token and authenticates the user."""
    try:
        email = verify_magic_link_token(req.token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or expired magic link: {str(exc)}",
        ) from exc

    stmt = select(User).where(User.email == email)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    tenant_stmt = select(Tenant).where(Tenant.id == user.tenant_id)
    tenant = (await session.execute(tenant_stmt)).scalar_one_or_none()

    token = create_access_token(
        data={"sub": user.id, "tenant_id": user.tenant_id, "email": user.email}
    )
    set_session_cookie(response, token)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        tenant=TenantInfo.model_validate(tenant),
        access_token=token,
    )
