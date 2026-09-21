"""Batch Apply Pipeline API Router (F8, BA-01..04)."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.batches import BatchError, batch_service

router = APIRouter(prefix="/api/batches", tags=["Batches"])


class BatchCreateRequest(BaseModel):
    job_ids: List[str]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_batch(
    req: BatchCreateRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Initializes a new batch apply group (BA-01)."""
    try:
        batch = await batch_service.create_batch(session, tenant_id, req.job_ids)
        await session.commit()
        return {"batch_id": batch.id, "total_jobs": batch.total_jobs, "status": batch.status}
    except BatchError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{batch_id}/preview")
async def get_batch_preview(
    batch_id: str,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """BA-04: Retrieves batch preview displaying per-job version, channel, and risk indicators."""
    try:
        preview = await batch_service.generate_batch_preview(session, tenant_id, batch_id)
        await session.commit()
        return preview
    except BatchError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{batch_id}/approve")
async def approve_batch(
    batch_id: str,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Approves a batch after candidate inspects preview screen."""
    try:
        batch = await batch_service.approve_batch(session, tenant_id, batch_id)
        await session.commit()
        return {"batch_id": batch.id, "status": batch.status}
    except BatchError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{batch_id}/execute")
async def execute_batch(
    batch_id: str,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Executes approved batch with concurrency caps and crash resilience (BA-01..03, RT-01)."""
    try:
        batch = await batch_service.execute_batch(session, tenant_id, batch_id)
        await session.commit()
        return {
            "batch_id": batch.id,
            "status": batch.status,
            "completed_at": batch.completed_at,
        }
    except BatchError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
