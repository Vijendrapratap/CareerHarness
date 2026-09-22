from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.journey import get_or_create_journey, refresh_stage_from_readiness

router = APIRouter(prefix="/api/journey", tags=["Candidate Journey"])


@router.get("")
async def get_journey(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    journey = await get_or_create_journey(db, tenant_id)
    return {"stage": journey.stage}


@router.post("/refresh")
async def refresh_journey(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    new_stage = await refresh_stage_from_readiness(db, tenant_id)
    return {"stage": new_stage}
