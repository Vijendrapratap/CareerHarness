"""Resume Intake & Skill Confirmation API Router."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.resume_parser import resume_parser

router = APIRouter(prefix="/api/resumes", tags=["Resumes"])


class ResumeUploadRequest(BaseModel):
    filename: str
    content: str


class ResumeResponse(BaseModel):
    id: str
    filename: str
    confidence_score: float
    extracted_skills: List[Dict[str, Any]]
    metrics: List[Dict[str, Any]]


@router.post("/upload", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    req: ResumeUploadRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Parses resume text into sections, metrics, and unverified skills (AT-06, ON-03)."""
    parsed = await resume_parser.parse_resume_text(
        session=session,
        tenant_id=tenant_id,
        filename=req.filename,
        content=req.content,
    )
    await session.commit()
    return ResumeResponse(
        id=parsed.id,
        filename=parsed.filename,
        confidence_score=parsed.confidence_score,
        extracted_skills=parsed.extracted_skills,
        metrics=parsed.metrics,
    )


@router.post("/{resume_id}/skills/{skill_name}/confirm", response_model=ResumeResponse)
async def confirm_skill(
    resume_id: str,
    skill_name: str,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Candidate explicitly confirms a skill to verified status (AT-06)."""
    try:
        updated = await resume_parser.confirm_skill(
            session=session,
            tenant_id=tenant_id,
            parse_id=resume_id,
            skill_name=skill_name,
        )
        await session.commit()
        return ResumeResponse(
            id=updated.id,
            filename=updated.filename,
            confidence_score=updated.confidence_score,
            extracted_skills=updated.extracted_skills,
            metrics=updated.metrics,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
