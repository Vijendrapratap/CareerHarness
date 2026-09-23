"""Browser auto-fill: start a session, review what was filled, answer what's missing, approve."""

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.apply_sessions import (
    ApplyError,
    approve,
    fill_in_background,
    save_answers,
    session_dict,
    start_session,
)
from app.domain.models import ApplySession

router = APIRouter(prefix="/api/apply", tags=["Auto-fill Apply"])


class StartRequest(BaseModel):
    job_id: str
    mode: str = "original"
    resume_version_id: Optional[str] = None


class AnswersRequest(BaseModel):
    answers: Dict[str, Any] = {}
    profile: Dict[str, str] = {}


async def _owned(db: AsyncSession, tenant_id: str, session_id: str) -> ApplySession:
    s = await db.get(ApplySession, session_id)
    if s is None or s.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application session not found.")
    return s


@router.post("/sessions", status_code=status.HTTP_202_ACCEPTED)
async def create_session(req: StartRequest, background_tasks: BackgroundTasks,
                         tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db)):
    try:
        s = await start_session(db, tenant_id, req.job_id, req.mode, req.resume_version_id)
    except ApplyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    await db.commit()
    if s.status == "filling":
        background_tasks.add_task(fill_in_background, s.id, False)
    return session_dict(s)


@router.get("/sessions/{session_id}")
async def read_session(session_id: str, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db)):
    return session_dict(await _owned(db, tenant_id, session_id))


@router.get("/sessions/{session_id}/screenshot")
async def screenshot(session_id: str, tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db)):
    s = await _owned(db, tenant_id, session_id)
    if not s.screenshot_path or not Path(s.screenshot_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No screenshot yet.")
    return FileResponse(s.screenshot_path, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/sessions/{session_id}/answers")
async def answer_questions(session_id: str, req: AnswersRequest, background_tasks: BackgroundTasks,
                           tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db)):
    s = await _owned(db, tenant_id, session_id)
    await save_answers(db, s, req.answers, req.profile)
    await db.commit()
    background_tasks.add_task(fill_in_background, s.id, False)
    return session_dict(s)


@router.post("/sessions/{session_id}/approve", status_code=status.HTTP_202_ACCEPTED)
async def approve_session(session_id: str, background_tasks: BackgroundTasks,
                          tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db)):
    s = await _owned(db, tenant_id, session_id)
    try:
        await approve(db, s)
    except ApplyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    await db.commit()
    background_tasks.add_task(fill_in_background, s.id, True)
    return session_dict(s)
