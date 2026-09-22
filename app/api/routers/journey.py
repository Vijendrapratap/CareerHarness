from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.journey import (
    JourneyRegressionError,
    Stage,
    get_or_create_journey,
    refresh_stage_from_readiness,
    set_stage,
)

router = APIRouter(prefix="/api/journey", tags=["Candidate Journey"])


class JourneyStageRequest(BaseModel):
    stage: Stage


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


@router.post("/stage")
async def update_journey_stage(
    request: JourneyStageRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        journey = await set_stage(db, tenant_id, request.stage)
        return {"stage": journey.stage}
    except JourneyRegressionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
