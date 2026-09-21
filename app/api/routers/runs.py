"""Agent Runs and Approval Management API Router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.models import Run
from app.domain.schemas import (
    ApprovalResolveRequest,
    ApprovalResponse,
    RunCreateRequest,
    RunResponse,
)
from app.harness.gate import gate

router = APIRouter(prefix="/api/runs", tags=["Runs & Approvals"])


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    req: RunCreateRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Initializes a new Agent Run."""
    run = Run(
        tenant_id=tenant_id,
        agent_name=req.agent_name,
        goal=req.goal,
        status="running",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    return RunResponse(
        id=run.id,
        tenant_id=run.tenant_id,
        agent_name=run.agent_name,
        goal=run.goal,
        status=run.status,
        step_count=run.step_count,
        pause_reason=run.pause_reason,
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves current execution status of an agent run."""
    query = select(Run).where(Run.id == run_id, Run.tenant_id == tenant_id)
    run = (await session.execute(query)).scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found for this tenant.",
        )

    return RunResponse(
        id=run.id,
        tenant_id=run.tenant_id,
        agent_name=run.agent_name,
        goal=run.goal,
        status=run.status,
        step_count=run.step_count,
        pause_reason=run.pause_reason,
    )


@router.post("/{run_id}/approvals/{approval_id}", response_model=ApprovalResponse)
async def resolve_approval(
    run_id: str,
    approval_id: str,
    req: ApprovalResolveRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Resolves an external action approval (HITL Gate)."""
    try:
        approval = await gate.resolve_approval(
            session=session,
            approval_id=approval_id,
            tenant_id=tenant_id,
            approved=req.approved,
        )
        await session.commit()
        return ApprovalResponse(
            id=approval.id,
            tenant_id=approval.tenant_id,
            run_id=approval.run_id,
            tool_name=approval.tool_name,
            status=approval.status,
            resolved_at=approval.resolved_at,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
