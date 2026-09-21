"""API router for Insights & Settings Management (F12)."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.insights import (
    PlanUpgradeRequiredError,
    ReadinessGateNotMetError,
    SettingsError,
    disconnect_mailbox,
    get_funnel_analytics,
    get_settings_summary,
    toggle_trusted_mode,
    update_scout_cadence,
)

router = APIRouter(prefix="/api/insights", tags=["Insights"])


class TrustedModeRequest(BaseModel):
    enable: bool


class CadenceRequest(BaseModel):
    cadence: str  # "daily" or "hourly"


@router.get("/funnel")
async def get_funnel_endpoint(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get funnel metrics and conversion rates across portals and resume versions (BT-01)."""
    return await get_funnel_analytics(session, tenant_id)


@router.post("/trusted-mode")
async def toggle_trusted_mode_endpoint(
    req: TrustedModeRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Toggle Trusted Mode with readiness score gate validation (BT-02)."""
    try:
        tenant = await toggle_trusted_mode(session, tenant_id, req.enable)
    except ReadinessGateNotMetError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except SettingsError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return {
        "tenant_id": tenant.id,
        "trusted_mode": tenant.trusted_mode,
    }


@router.patch("/cadence")
async def update_cadence_endpoint(
    req: CadenceRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update Scout scanning cadence (BT-03)."""
    try:
        sched = await update_scout_cadence(session, tenant_id, req.cadence)
    except PlanUpgradeRequiredError as e:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(e)) from e
    except SettingsError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return {
        "cadence": sched.cadence,
        "is_active": sched.is_active,
    }


@router.delete("/email")
async def disconnect_email_endpoint(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Disconnect and revoke connected email mailbox (BT-03)."""
    disconnected = await disconnect_mailbox(session, tenant_id)
    return {
        "disconnected": disconnected,
    }


@router.get("/settings")
async def get_settings_endpoint(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get complete settings summary (BT-03)."""
    try:
        return await get_settings_summary(session, tenant_id)
    except SettingsError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
