"""Scout Agent Trigger & Scheduler API Router (F7, RD-02, RD-03)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.readiness import ReadinessGateBlockedError
from app.domain.scout import ScoutRateLimitError, scout_scheduler

router = APIRouter(prefix="/api/scout", tags=["Scout Agent"])


@router.post("/auto-schedule")
async def auto_schedule_scout(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Auto-schedules autonomous Scout cron upon passing Readiness Gate (RD-02)."""
    try:
        schedule = await scout_scheduler.auto_schedule_on_gate_pass(session, tenant_id)
        await session.commit()
        return {"status": "scheduled", "cadence": schedule.cadence, "active": schedule.is_active}
    except ReadinessGateBlockedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/scan-now")
async def scan_now(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Triggers an on-demand Scout scan subject to plan limits (RD-03: 3/day Free, 10/day Pro)."""
    try:
        result = await scout_scheduler.trigger_manual_scan(session, tenant_id)
        await session.commit()
        return result
    except ReadinessGateBlockedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ScoutRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
