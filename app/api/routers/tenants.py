"""Tenant management API routes for onboarding and demo testing."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domain.models import Tenant

router = APIRouter(prefix="/api/tenants", tags=["Tenants"])


class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Candidate or organization name")
    plan: str = Field(default="pro", description="'free' or 'pro'")
    trusted_mode: bool = Field(default=False, description="Enable automated trusted mode")


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    plan: str
    trusted_mode: bool
    is_active: bool


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    req: TenantCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Creates a new tenant account with an isolated HKDF key namespace and RLS boundary."""
    tenant = Tenant(
        name=req.name,
        plan=req.plan.lower(),
        trusted_mode=req.trusted_mode,
        is_active=True,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.get("/demo", response_model=TenantResponse)
async def get_or_create_demo_tenant(
    db: AsyncSession = Depends(get_db),
):
    """Returns a ready-to-use demo tenant for instant interactive testing."""
    stmt = select(Tenant).where(Tenant.name == "Demo Candidate").limit(1)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()

    if not tenant:
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name="Demo Candidate",
            plan="pro",
            trusted_mode=False,
            is_active=True,
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)

    return tenant


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetches tenant profile details."""
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found.",
        )
    return tenant
