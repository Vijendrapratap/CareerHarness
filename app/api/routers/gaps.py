"""Gap Engine, To-Dos, and Readiness Gate API Router."""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.gap_engine import GapEngineError, gap_engine
from app.domain.models import TodoItem
from app.domain.readiness import readiness_gate

router = APIRouter(tags=["Gaps & Readiness"])


class TodoActionRequest(BaseModel):
    action: str  # "accept", "edit", "dismiss"
    edited_text: Optional[str] = None
    dismiss_reason: Optional[str] = None


class TodoItemResponse(BaseModel):
    id: str
    category: str
    severity: str
    issue_text: str
    why_it_matters: str
    fix_draft: str
    source_bullet: Optional[str] = None
    has_unverified_metric: bool
    status: str
    dismiss_reason: Optional[str] = None


class ReadinessResponse(BaseModel):
    is_ready: bool
    overall_score: int
    open_criticals: int
    is_capped: bool
    cap_reason: Optional[str] = None
    unblocking_todos: List[Dict[str, str]]


@router.post("/api/gaps/compute")
async def compute_gaps(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Computes presentation gaps, honest skill gaps, and Front-Face Score (F5)."""
    try:
        report, todos, score = await gap_engine.compute_gaps(session, tenant_id)
        await session.commit()
        return {
            "overall_score": score.overall_score,
            "is_capped_at_69": score.is_capped_at_69,
            "cap_reason": score.cap_reason,
            "total_todos": len(todos),
            "open_criticals": sum(1 for t in todos if t.severity == "critical" and t.status == "open"),
        }
    except GapEngineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/api/todos", response_model=List[TodoItemResponse])
async def list_todos(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Lists to-do fix items sorted by severity (critical > major > minor)."""
    query = select(TodoItem).where(TodoItem.tenant_id == tenant_id)
    records = (await session.execute(query)).scalars().all()
    # Sort priority
    sev_rank = {"critical": 0, "major": 1, "minor": 2}
    sorted_records = sorted(records, key=lambda x: (sev_rank.get(x.severity, 3), x.status != "open"))

    return [
        TodoItemResponse(
            id=r.id,
            category=r.category,
            severity=r.severity,
            issue_text=r.issue_text,
            why_it_matters=r.why_it_matters,
            fix_draft=r.fix_draft,
            source_bullet=r.source_bullet,
            has_unverified_metric=r.has_unverified_metric,
            status=r.status,
            dismiss_reason=r.dismiss_reason,
        )
        for r in sorted_records
    ]


@router.post("/api/todos/{todo_id}/action", response_model=TodoItemResponse)
async def resolve_todo_action(
    todo_id: str,
    req: TodoActionRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Resolves to-do card (Accept, Edit, Dismiss with reason) and recomputes score (GE-03, GE-05)."""
    try:
        todo, score = await gap_engine.resolve_todo(
            session=session,
            tenant_id=tenant_id,
            todo_id=todo_id,
            action=req.action,
            edited_text=req.edited_text,
            dismiss_reason=req.dismiss_reason,
        )
        await session.commit()
        return TodoItemResponse(
            id=todo.id,
            category=todo.category,
            severity=todo.severity,
            issue_text=todo.issue_text,
            why_it_matters=todo.why_it_matters,
            fix_draft=todo.fix_draft,
            source_bullet=todo.source_bullet,
            has_unverified_metric=todo.has_unverified_metric,
            status=todo.status,
            dismiss_reason=todo.dismiss_reason,
        )
    except GapEngineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/api/readiness", response_model=ReadinessResponse)
async def get_readiness_status(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Returns candidate readiness status, score, and unblocking items (F7)."""
    status_obj = await readiness_gate.evaluate_readiness(session, tenant_id)
    return ReadinessResponse(
        is_ready=status_obj.is_ready,
        overall_score=status_obj.overall_score,
        open_criticals=status_obj.open_criticals,
        is_capped=status_obj.is_capped,
        cap_reason=status_obj.cap_reason,
        unblocking_todos=status_obj.unblocking_todos,
    )
