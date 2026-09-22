"""Scout Agent Trigger & Scheduler API Router (F7, RD-02, RD-03)."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.scout import ScoutRateLimitError, scan_in_background, scout_scheduler

router = APIRouter(prefix="/api/scout", tags=["Scout Agent"])


@router.post("/auto-schedule")
async def auto_schedule_scout(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Activates the autonomous Scout cadence."""
    schedule = await scout_scheduler.auto_schedule_on_gate_pass(session, tenant_id)
    await session.commit()
    return {"status": "scheduled", "cadence": schedule.cadence, "active": schedule.is_active}


@router.post("/scan-now")
async def scan_now(
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Starts an on-demand Scout scan subject to plan limits (RD-03: 3/day Free, 10/day Pro).

    The scan covers dozens of sources and can take longer than a proxy timeout, so it runs after
    the response; the Jobs page polls for new matches.
    """
    try:
        result = await scout_scheduler.trigger_manual_scan(session, tenant_id)
        await session.commit()
        background_tasks.add_task(scan_in_background, tenant_id)
        return {**result, "status": "scanning"}
    except ScoutRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
