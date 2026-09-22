"""Resume Intake & Skill Confirmation API Router."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.resume_parser import resume_parser
from app.domain.vault import create_initial_master, get_master_version

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
    request: Request,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Parses resume from either multipart file upload (PDF/text) or JSON payload (AT-06, ON-03)."""
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        if not uploaded_file:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No file provided in form upload.",
            )

        filename = getattr(uploaded_file, "filename", "resume.pdf") or "resume.pdf"
        file_bytes = await uploaded_file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        is_pdf = filename.lower().endswith(".pdf") or file_bytes.startswith(b"%PDF")
        if is_pdf:
            try:
                parsed = await resume_parser.parse_pdf_bytes(
                    session=session,
                    tenant_id=tenant_id,
                    filename=filename,
                    pdf_bytes=file_bytes,
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to parse PDF binary: {str(e)}",
                )
        else:
            text = file_bytes.decode("utf-8", errors="replace")
            parsed = await resume_parser.parse_resume_text(
                session=session,
                tenant_id=tenant_id,
                filename=filename,
                content=text,
            )
    else:
        # JSON body handling
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request format. Expected JSON or multipart/form-data.",
            )
        filename = body.get("filename", "master_resume.txt")
        content = body.get("content", "")
        if not content:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Resume content cannot be empty.",
            )
        parsed = await resume_parser.parse_resume_text(
            session=session,
            tenant_id=tenant_id,
            filename=filename,
            content=content,
        )

    # Ensure a master DocumentVersion exists in the vault for downstream applications
    master = await get_master_version(session, tenant_id, "resume")
    if not master:
        content_dict = {
            "summary": parsed.sections.get("summary", "") if parsed.sections else "",
            "bullets": parsed.sections.get("bullets", []) if parsed.sections else [],
            "skills": [s["name"] for s in (parsed.extracted_skills or [])],
            "raw_text": parsed.raw_text,
        }
        await create_initial_master(
            session=session,
            tenant_id=tenant_id,
            title=parsed.filename or "Master Resume",
            content=content_dict,
            raw_markdown=parsed.raw_text,
            document_type="resume",
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
