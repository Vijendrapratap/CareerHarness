"""API router for Application Tracking and Outreach Loop (F11)."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.models import ApplicationTrack, JobListing
from app.domain.tracker import (
    OutreachConsentMissingError,
    OutreachRateLimitExceededError,
    TrackerError,
    create_outreach_draft,
    detect_silence_and_mark_ghosted,
    process_inbound_email,
    send_outreach_message,
    track_application,
    update_application_status,
)

router = APIRouter(prefix="/api/tracker", tags=["Tracker"])


class TrackApplicationRequest(BaseModel):
    job_id: str
    resume_version_id: Optional[str] = None
    status: str = "applied"


class UpdateStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None


class InboundEmailRequest(BaseModel):
    sender_email: str
    subject: str
    body_text: str
    application_id: Optional[str] = None


class OutreachDraftRequest(BaseModel):
    recipient_name: str
    recipient_email: str
    recipient_role: str = "Hiring Manager"
    company_name: str
    job_title: str
    candidate_name: str
    pitch_bullets: List[str] = Field(default_factory=list)
    application_id: Optional[str] = None


class SendOutreachRequest(BaseModel):
    bypass_approval: bool = False


@router.post("/track")
async def track_application_endpoint(
    req: TrackApplicationRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Record an application in the tracking loop."""
    job_stmt = select(JobListing).where(JobListing.id == req.job_id)
    job_res = await session.execute(job_stmt)
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    app_track = await track_application(
        session=session,
        tenant_id=tenant_id,
        job=job,
        resume_version_id=req.resume_version_id,
        status=req.status,
    )
    return {
        "id": app_track.id,
        "company_name": app_track.company_name,
        "job_title": app_track.job_title,
        "status": app_track.status,
        "applied_at": app_track.applied_at.isoformat(),
    }


@router.patch("/{application_id}/status")
async def update_status_endpoint(
    application_id: str,
    req: UpdateStatusRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update tracked application status and synchronize outcome to vault."""
    try:
        app_track = await update_application_status(
            session=session,
            tenant_id=tenant_id,
            application_id=application_id,
            new_status=req.status,
            notes=req.notes,
        )
    except TrackerError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return {
        "id": app_track.id,
        "status": app_track.status,
        "last_activity_at": app_track.last_activity_at.isoformat(),
    }


@router.get("/applications")
async def list_tracked_applications_endpoint(
    status_filter: Optional[str] = None,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List tracked applications for tenant."""
    stmt = select(ApplicationTrack).where(ApplicationTrack.tenant_id == tenant_id)
    if status_filter:
        stmt = stmt.where(ApplicationTrack.status == status_filter)
    stmt = stmt.order_by(ApplicationTrack.last_activity_at.desc())

    res = await session.execute(stmt)
    apps = list(res.scalars().all())

    return [
        {
            "id": a.id,
            "company_name": a.company_name,
            "job_title": a.job_title,
            "status": a.status,
            "resume_version_id": a.resume_version_id,
            "is_ghosted": a.is_ghosted,
            "applied_at": a.applied_at.isoformat(),
            "last_activity_at": a.last_activity_at.isoformat(),
        }
        for a in apps
    ]


@router.post("/inbound-email")
async def process_inbound_email_endpoint(
    req: InboundEmailRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Classify inbound email and auto-update application tracking state (GT-05)."""
    email_record = await process_inbound_email(
        session=session,
        tenant_id=tenant_id,
        sender_email=req.sender_email,
        subject=req.subject,
        body_text=req.body_text,
        application_id=req.application_id,
    )
    return {
        "id": email_record.id,
        "classification": email_record.classification,
        "confidence": email_record.confidence_score,
        "application_id": email_record.application_id,
    }


@router.post("/outreach/draft")
async def draft_outreach_endpoint(
    req: OutreachDraftRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Draft a personalized outreach email to a hiring manager."""
    msg = await create_outreach_draft(
        session=session,
        tenant_id=tenant_id,
        recipient_name=req.recipient_name,
        recipient_email=req.recipient_email,
        recipient_role=req.recipient_role,
        company_name=req.company_name,
        job_title=req.job_title,
        candidate_name=req.candidate_name,
        pitch_bullets=req.pitch_bullets,
        application_id=req.application_id,
    )
    return {
        "id": msg.id,
        "subject": msg.subject,
        "body_text": msg.body_text,
        "status": msg.status,
    }


@router.post("/outreach/{outreach_id}/send")
async def send_outreach_endpoint(
    outreach_id: str,
    req: SendOutreachRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Send outreach message enforcing consent (CT-03) and 15/day cap (GT-04)."""
    try:
        msg = await send_outreach_message(
            session=session,
            tenant_id=tenant_id,
            outreach_id=outreach_id,
            bypass_approval=req.bypass_approval,
        )
    except OutreachConsentMissingError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except OutreachRateLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)) from e
    except TrackerError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return {
        "id": msg.id,
        "status": msg.status,
        "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
    }


@router.post("/detect-ghosted")
async def detect_ghosted_endpoint(
    days: int = 10,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Detect and mark ghosted applications with silence > days (GT-05)."""
    ghosted = await detect_silence_and_mark_ghosted(session, tenant_id, days)
    return {
        "ghosted_count": len(ghosted),
        "ghosted_application_ids": [g.id for g in ghosted],
    }


@router.get("/inbox")
async def get_recruiter_inbox(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Returns conversation threads grouped by application."""
    from app.domain.inbox import list_recruiter_threads
    threads = await list_recruiter_threads(session, tenant_id)
    return {"threads": threads}
