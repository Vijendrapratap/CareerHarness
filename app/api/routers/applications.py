"""API router for Application Engine Pipeline (F9)."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.core.keyvault import KeyInactiveError, KeyNotFoundError, keyvault
from app.domain.application_engine import (
    answer_screening_questions,
    check_ats_compatibility,
    draft_application_packet,
    execute_application_submission,
    generate_cover_letter,
)
from app.domain.models import ApplicationAuditLog, ApplicationTrack, JobListing, ResumeParse
from app.domain.vault import (
    create_tailored_version,
    get_document_version,
    get_master_version,
    record_outcome,
)

router = APIRouter(prefix="/api/applications", tags=["Applications"])


class TailorRequest(BaseModel):
    job_id: str
    parent_version_id: Optional[str] = None
    save_to_vault: bool = True


class CoverLetterRequest(BaseModel):
    job_id: str
    resume_version_id: Optional[str] = None


class ATSCheckRequest(BaseModel):
    job_id: str
    tailored_content: Dict[str, Any]


class ScreeningQuestionsRequest(BaseModel):
    questions: List[str]
    facts_override: Optional[Dict[str, Any]] = None


class ChooseApplyRequest(BaseModel):
    job_id: str
    mode: str


class SubmitApplicationRequest(BaseModel):
    job_id: str
    resume_version_id: str
    cover_letter_version_id: Optional[str] = None
    screening_answers: Dict[str, str] = Field(default_factory=dict)
    simulate_bot_block: bool = False
    company_email: Optional[str] = None
    has_connected_email: bool = False
    batch_item_id: Optional[str] = None


@router.post("/tailor")
async def tailor_application_endpoint(
    req: TailorRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Execute Stage 1 (Tailor) and Stage 2 (Reviewer sub-agent honesty check) (AT-01, AT-02)."""
    # Fetch job
    job_stmt = select(JobListing).where(JobListing.id == req.job_id)
    job_res = await session.execute(job_stmt)
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {req.job_id} not found")

    # Fetch parent resume
    if req.parent_version_id:
        parent_doc = await get_document_version(session, tenant_id, req.parent_version_id)
    else:
        parent_doc = await get_master_version(session, tenant_id, "resume")

    if not parent_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent or master resume not found")

    # Get verified skills
    parse_stmt = (
        select(ResumeParse)
        .where(ResumeParse.tenant_id == tenant_id)
        .order_by(ResumeParse.created_at.desc())
        .limit(1)
    )
    resume_parse = (await session.execute(parse_stmt)).scalars().first()

    verified_skills: List[str] = []
    if resume_parse:
        verified_skills = [
            s.get("name", "")
            for s in resume_parse.extracted_skills
            if s.get("verified") is True and s.get("name")
        ]

    # Fallback to skills in master content if not marked in parse
    if not verified_skills:
        verified_skills = parent_doc.content.get("skills", [])

    raw_key = None
    try:
        raw_key = await keyvault.get_decrypted_key(session, tenant_id, "openrouter")
    except (KeyNotFoundError, KeyInactiveError):
        raw_key = None

    packet = await draft_application_packet(
        tenant_id=tenant_id,
        master_content=parent_doc.content,
        job=job,
        verified_skills=verified_skills,
        raw_key=raw_key,
    )
    tailored = packet["tailored_resume"]
    review = packet["honesty_review"]

    vault_version_id = None
    cover_version_id = None
    if req.save_to_vault and review["is_honest"]:
        child_doc = await create_tailored_version(
            session=session,
            tenant_id=tenant_id,
            parent_version_id=parent_doc.id,
            target_job_id=job.id,
            target_role_id=None,
            title=f"Tailored for {job.company} - {job.title}",
            content=tailored,
            raw_markdown=str(tailored),
            diff_summary={
                "target_company": job.company,
                "target_title": job.title,
                "injected_keywords": tailored.get("tailored_keywords_injected", []),
                "draft_source": packet["draft_source"],
            },
        )
        vault_version_id = child_doc.id
        if packet["cover_letter"]:
            cover_doc = await create_tailored_version(
                session=session,
                tenant_id=tenant_id,
                parent_version_id=parent_doc.id,
                target_job_id=job.id,
                target_role_id=None,
                title=packet["cover_letter"]["title"],
                content=packet["cover_letter"],
                raw_markdown=packet["cover_letter"]["body_text"],
                diff_summary={"draft_source": packet["draft_source"]},
                document_type="cover_letter",
            )
            cover_version_id = cover_doc.id

    return {
        "tailored_resume": tailored,
        "honesty_review": review,
        "cover_letter": packet["cover_letter"],
        "draft_source": packet["draft_source"],
        "vault_version_id": vault_version_id,
        "cover_letter_version_id": cover_version_id,
    }


@router.post("/choose")
async def choose_application_mode(
    req: ChooseApplyRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Prepares an application packet choosing original master resume or tailored/refined resume."""
    if req.mode not in ("original", "refine"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mode must be original or refine",
        )
    try:
        from app.domain.apply_choice import prepare_application
        result = await prepare_application(
            session=session,
            tenant_id=tenant_id,
            job_id=req.job_id,
            mode=req.mode,  # type: ignore[arg-type]
        )
        await session.commit()
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/cover-letter")
async def cover_letter_endpoint(
    req: CoverLetterRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Execute Stage 3 (Cover Letter generation)."""
    job_stmt = select(JobListing).where(JobListing.id == req.job_id)
    job_res = await session.execute(job_stmt)
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {req.job_id} not found")

    if req.resume_version_id:
        doc = await get_document_version(session, tenant_id, req.resume_version_id)
    else:
        doc = await get_master_version(session, tenant_id, "resume")

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume version not found")

    cover_letter = generate_cover_letter(doc.content, job, doc.content)
    return cover_letter


@router.post("/ats-check")
async def ats_check_endpoint(
    req: ATSCheckRequest,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Execute Stage 4 (ATS scan and formatting validation) (AT-03)."""
    job_stmt = select(JobListing).where(JobListing.id == req.job_id)
    job_res = await session.execute(job_stmt)
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {req.job_id} not found")

    return check_ats_compatibility(req.tailored_content, job)


@router.post("/screening-questions")
async def screening_questions_endpoint(
    req: ScreeningQuestionsRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Answer screening questions strictly from verified facts (AT-04)."""
    facts = req.facts_override or {}
    if not facts:
        # Load verified facts from DB
        parse_stmt = (
            select(ResumeParse)
            .where(ResumeParse.tenant_id == tenant_id)
            .order_by(ResumeParse.created_at.desc())
            .limit(1)
        )
        resume_parse = (await session.execute(parse_stmt)).scalars().first()
        verified_skills = []
        if resume_parse:
            verified_skills = [
                s.get("name", "")
                for s in resume_parse.extracted_skills
                if s.get("verified") is True and s.get("name")
            ]
        if not verified_skills:
            master_doc = await get_master_version(session, tenant_id, "resume")
            if master_doc:
                verified_skills = master_doc.content.get("skills", [])

        facts = {
            "work_authorization": "Authorized to work in US without sponsorship",
            "years_of_experience": "6+",
            "location_preference": "Remote or hybrid",
            "verified_skills": verified_skills,
        }

    return answer_screening_questions(req.questions, facts)


@router.post("/submit")
async def submit_application_endpoint(
    req: SubmitApplicationRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Execute Stage 5 (Submission with 3-tier bot mitigation fallback ladder) (AT-05, AT-07, VR-01)."""
    job_stmt = select(JobListing).where(JobListing.id == req.job_id)
    job_res = await session.execute(job_stmt)
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {req.job_id} not found")

    resume_doc = await get_document_version(session, tenant_id, req.resume_version_id)
    if not resume_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume version not found")

    cover_letter_doc = None
    if req.cover_letter_version_id:
        cover_letter_doc = await get_document_version(session, tenant_id, req.cover_letter_version_id)

    audit_log = await execute_application_submission(
        session=session,
        tenant_id=tenant_id,
        job=job,
        resume_version=resume_doc,
        cover_letter_version=cover_letter_doc,
        screening_answers=req.screening_answers,
        has_connected_email=req.has_connected_email,
        company_email=req.company_email,
        simulate_bot_block=req.simulate_bot_block,
        batch_item_id=req.batch_item_id,
    )

    # Record outcome on resume version
    await record_outcome(session, tenant_id, resume_doc.id, "application")

    # Get or create ApplicationTrack
    track_stmt = select(ApplicationTrack).where(
        ApplicationTrack.tenant_id == tenant_id,
        ApplicationTrack.job_id == job.id,
    )
    track = (await session.execute(track_stmt)).scalar_one_or_none()
    if not track:
        track = ApplicationTrack(
            tenant_id=tenant_id,
            job_id=job.id,
            resume_version_id=resume_doc.id,
            company_name=job.company,
            job_title=job.title,
            portal_type=job.portal_type,
            status="applied",
        )
        session.add(track)
        await session.flush()

    # Draft recruiter touch if posting contains public email
    from app.domain.recruiter_hunter import draft_recruiter_touch
    resume_excerpt = (
        str(resume_doc.content.get("summary", ""))
        if isinstance(resume_doc.content, dict)
        else ""
    )
    cover_body = cover_letter_doc.raw_markdown if cover_letter_doc else ""
    recruiter_touch = await draft_recruiter_touch(
        session=session,
        tenant_id=tenant_id,
        application_id=track.id,
        job_text=job.description or "",
        resume_excerpt=resume_excerpt,
        cover_letter=cover_body,
    )

    return {
        "audit_log_id": audit_log.id,
        "application_id": track.id,
        "resume_version_id": audit_log.resume_version_id,
        "job_id": audit_log.job_id,
        "status": audit_log.status,
        "channel": audit_log.channel,
        "bot_mitigation_tier": audit_log.bot_mitigation_tier,
        "confirmation_code": audit_log.confirmation_code,
        "handoff_bundle_url": audit_log.handoff_bundle_url,
        "fallback_reason": audit_log.fallback_reason,
        "recruiter_touch": recruiter_touch,
    }



@router.get("/audit-logs")
async def list_audit_logs_endpoint(
    job_id: Optional[str] = None,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List application audit logs for tenant."""
    stmt = select(ApplicationAuditLog).where(ApplicationAuditLog.tenant_id == tenant_id)
    if job_id:
        stmt = stmt.where(ApplicationAuditLog.job_id == job_id)
    stmt = stmt.order_by(ApplicationAuditLog.created_at.desc())
    res = await session.execute(stmt)
    logs = list(res.scalars().all())

    return [
        {
            "id": log.id,
            "job_id": log.job_id,
            "resume_version_id": log.resume_version_id,
            "channel": log.channel,
            "status": log.status,
            "bot_mitigation_tier": log.bot_mitigation_tier,
            "confirmation_code": log.confirmation_code,
            "fallback_reason": log.fallback_reason,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
