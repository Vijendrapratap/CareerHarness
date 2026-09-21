"""Application Tracking & Outreach Loop Engine (F11).

Provides:
- Application tracking & lifecycle management.
- Recruiter reply classification (interview, assessment, rejection, request_info) (GT-05).
- Silence detector for ghosted applications (>10 days) (GT-05).
- Personalized hiring manager outreach drafting.
- Outreach daily rate cap enforcement (<= 15/day) (GT-04) and consent checks (CT-03).
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    ApplicationTrack,
    Consent,
    InboundEmail,
    JobListing,
    OutreachMessage,
    Tenant,
)
from app.domain.vault import record_outcome


class TrackerError(Exception):
    """Base exception for tracker operations."""
    pass


class OutreachRateLimitExceededError(TrackerError):
    """Raised when tenant exceeds 15 outreach emails per day (GT-04)."""
    pass


class OutreachConsentMissingError(TrackerError):
    """Raised when outreach is attempted without email outreach consent (CT-03)."""
    pass


# ============================================================================
# APPLICATION TRACKING LIFECYCLE
# ============================================================================

async def track_application(
    session: AsyncSession,
    tenant_id: str,
    job: JobListing,
    resume_version_id: Optional[str] = None,
    status: str = "applied",
) -> ApplicationTrack:
    """Record new application in tracking loop."""
    now = datetime.now(timezone.utc)
    track = ApplicationTrack(
        tenant_id=tenant_id,
        job_id=job.id,
        resume_version_id=resume_version_id,
        company_name=job.company,
        job_title=job.title,
        portal_type=job.portal_type,
        status=status,
        applied_at=now,
        last_activity_at=now,
        is_ghosted=False,
    )
    session.add(track)
    await session.flush()
    return track


async def update_application_status(
    session: AsyncSession,
    tenant_id: str,
    application_id: str,
    new_status: str,
    notes: Optional[str] = None,
) -> ApplicationTrack:
    """Update status of tracked application and synchronize outcome to vault if applicable."""
    stmt = select(ApplicationTrack).where(
        ApplicationTrack.id == application_id,
        ApplicationTrack.tenant_id == tenant_id,
    )
    res = await session.execute(stmt)
    track = res.scalar_one_or_none()
    if not track:
        raise TrackerError(f"Application {application_id} not found")

    track.status = new_status
    track.last_activity_at = datetime.now(timezone.utc)
    if notes:
        track.notes = notes

    # Synchronize outcome metrics with vault document version
    if track.resume_version_id:
        if new_status == "interview":
            await record_outcome(session, tenant_id, track.resume_version_id, "interview")
        elif new_status == "rejected":
            await record_outcome(session, tenant_id, track.resume_version_id, "rejection")
        elif new_status == "offer":
            await record_outcome(session, tenant_id, track.resume_version_id, "offer")

    await session.flush()
    return track


async def detect_silence_and_mark_ghosted(
    session: AsyncSession,
    tenant_id: str,
    days_threshold: int = 10,
) -> List[ApplicationTrack]:
    """Flag applications with silence > 10 days as ghosted (GT-05)."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_threshold)

    stmt = select(ApplicationTrack).where(
        ApplicationTrack.tenant_id == tenant_id,
        ApplicationTrack.status.in_(["applied", "acknowledged"]),
        ApplicationTrack.last_activity_at <= cutoff,
        ApplicationTrack.is_ghosted.is_(False),
    )
    res = await session.execute(stmt)
    ghosted_apps = list(res.scalars().all())

    for app in ghosted_apps:
        app.is_ghosted = True
        app.status = "ghosted"

    await session.flush()
    return ghosted_apps


# ============================================================================
# REPLY CLASSIFICATION (GT-05)
# ============================================================================

def classify_inbound_email(subject: str, body_text: str) -> Dict[str, Any]:
    """Classify recruiter/company inbound email into categories (GT-05).

    Categories:
    - interview: scheduling chat, phone screen, calendly/goodtime links.
    - assessment: take-home coding, hackerrank, codility test.
    - rejection: not moving forward, pursuing other candidates.
    - request_info: salary expectations, availability, work auth docs.
    - other: general correspondence.
    """
    text = (subject + " " + body_text).lower()

    if any(k in text for k in [
        "schedule an interview",
        "phone screen",
        "chat with the team",
        "calendly.com",
        "goodtime.io",
        "invite you for an interview",
        "next steps: interview",
    ]):
        return {"classification": "interview", "confidence": 0.98}

    if any(k in text for k in [
        "take-home",
        "coding challenge",
        "hackerrank",
        "codility",
        "technical assessment",
        "online assessment",
        "skill evaluation",
    ]):
        return {"classification": "assessment", "confidence": 0.95}

    if any(k in text for k in [
        "not moving forward",
        "unfortunately",
        "pursuing other candidates",
        "impressed with your background, however",
        "decided not to proceed",
        "position has been filled",
    ]):
        return {"classification": "rejection", "confidence": 0.99}

    if any(k in text for k in [
        "salary expectation",
        "confirm your availability",
        "right to work",
        "work authorization document",
        "earliest start date",
    ]):
        return {"classification": "request_info", "confidence": 0.92}

    return {"classification": "other", "confidence": 0.80}


async def process_inbound_email(
    session: AsyncSession,
    tenant_id: str,
    sender_email: str,
    subject: str,
    body_text: str,
    application_id: Optional[str] = None,
) -> InboundEmail:
    """Classify inbound email and auto-update application tracking state."""
    cls_result = classify_inbound_email(subject, body_text)
    classification = cls_result["classification"]

    inbound = InboundEmail(
        tenant_id=tenant_id,
        sender_email=sender_email,
        subject=subject,
        body_text=body_text,
        classification=classification,
        confidence_score=cls_result["confidence"],
        application_id=application_id,
    )
    session.add(inbound)

    # Auto-advance application status if linked
    if application_id:
        if classification == "interview":
            await update_application_status(session, tenant_id, application_id, "interview")
        elif classification == "assessment":
            await update_application_status(session, tenant_id, application_id, "assessment")
        elif classification == "rejection":
            await update_application_status(session, tenant_id, application_id, "rejected")

    await session.flush()
    return inbound


# ============================================================================
# OUTREACH ENGINE & RATE LIMITS (GT-01, GT-04, CT-03)
# ============================================================================

async def create_outreach_draft(
    session: AsyncSession,
    tenant_id: str,
    recipient_name: str,
    recipient_email: str,
    recipient_role: str,
    company_name: str,
    job_title: str,
    candidate_name: str,
    pitch_bullets: List[str],
    application_id: Optional[str] = None,
) -> OutreachMessage:
    """Draft personalized outreach message for candidate review."""
    subject = f"Excited about {job_title} role at {company_name} - {candidate_name}"
    bullets_text = "\n".join([f"• {b}" for b in pitch_bullets[:2]])
    body = (
        f"Hi {recipient_name},\n\n"
        f"I recently applied for the {job_title} position at {company_name} and wanted to reach out directly. "
        f"I admire what your team is building.\n\n"
        f"A couple of quick highlights from my background:\n"
        f"{bullets_text}\n\n"
        f"I'd welcome the opportunity to chat if you have a few minutes this week.\n\n"
        f"Best regards,\n{candidate_name}"
    )

    msg = OutreachMessage(
        tenant_id=tenant_id,
        application_id=application_id,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        recipient_role=recipient_role,
        subject=subject,
        body_text=body,
        status="draft",
    )
    session.add(msg)
    await session.flush()
    return msg


async def send_outreach_message(
    session: AsyncSession,
    tenant_id: str,
    outreach_id: str,
    bypass_approval: bool = False,
) -> OutreachMessage:
    """Send outreach message enforcing consent (CT-03), rate limits <=15/day (GT-04), and gates (GT-01..03)."""
    # 1. Verify outreach consent (CT-03)
    consent_stmt = select(Consent).where(
        Consent.tenant_id == tenant_id,
        Consent.consent_type == "email_connect",
    )
    consent_res = await session.execute(consent_stmt)
    consent = consent_res.scalar_one_or_none()
    if not consent:
        raise OutreachConsentMissingError("Candidate has not granted email outreach consent (CT-03)")

    # 2. Check 15 emails/day cap (GT-04)
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    count_stmt = select(func.count(OutreachMessage.id)).where(
        OutreachMessage.tenant_id == tenant_id,
        OutreachMessage.status == "sent",
        OutreachMessage.sent_at >= today_start,
    )
    sent_count_res = await session.execute(count_stmt)
    sent_today = sent_count_res.scalar() or 0

    if sent_today >= 15:
        raise OutreachRateLimitExceededError(
            f"Daily outreach limit reached ({sent_today}/15 emails sent today). GT-04 strictly enforced."
        )

    # 3. Fetch message
    msg_stmt = select(OutreachMessage).where(
        OutreachMessage.id == outreach_id,
        OutreachMessage.tenant_id == tenant_id,
    )
    msg_res = await session.execute(msg_stmt)
    msg = msg_res.scalar_one_or_none()
    if not msg:
        raise TrackerError(f"Outreach message {outreach_id} not found")

    # 4. Check tenant trusted mode (GT-01, GT-02)
    tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
    tenant_res = await session.execute(tenant_stmt)
    tenant = tenant_res.scalar_one_or_none()
    is_trusted = tenant.trusted_mode if tenant else False

    if not is_trusted and not bypass_approval:
        # Requires human-in-the-loop gate approval (GT-01)
        msg.status = "pending_approval"
        await session.flush()
        return msg

    # Send message (simulated transmission via connected mailbox)
    msg.status = "sent"
    msg.sent_at = now
    await session.flush()
    return msg


def calculate_interview_reminders(
    interview_time: datetime,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Calculates T-24h and T-1h notification trigger timestamps for an upcoming interview."""
    if now is None:
        now = datetime.now(timezone.utc)
    if interview_time.tzinfo is None:
        interview_time = interview_time.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    t_minus_24h = interview_time - timedelta(hours=24)
    t_minus_1h = interview_time - timedelta(hours=1)

    return {
        "interview_time": interview_time.isoformat(),
        "reminder_24h_at": t_minus_24h.isoformat(),
        "reminder_1h_at": t_minus_1h.isoformat(),
        "should_send_24h": (now >= t_minus_24h and now < t_minus_1h),
        "should_send_1h": (now >= t_minus_1h and now < interview_time),
        "is_past": now >= interview_time,
    }
