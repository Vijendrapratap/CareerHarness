"""Interview Calendar & Reminders Service (Task 12).

Detects and records interview events from recruiter communication
and emits 24-hour and 1-hour automated reminders.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models import ApplicationTrack, InterviewEvent, OutreachMessage, User


def due_reminders(event: Any, now: datetime) -> List[str]:
    """Returns a subset of ["24h", "1h"] due at the current timestamp."""
    # Ensure timezone awareness for comparison
    evt_start = event.starts_at
    if evt_start.tzinfo is None:
        evt_start = evt_start.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # After interview has started, no reminders are emitted
    if now >= evt_start:
        return []

    tokens: List[str] = []
    if not event.reminder_24h_sent and now >= (evt_start - timedelta(hours=24)):
        tokens.append("24h")
    if not event.reminder_1h_sent and now >= (evt_start - timedelta(hours=1)):
        tokens.append("1h")

    return tokens


async def record_interview(
    session: AsyncSession,
    tenant_id: str,
    application_id: str,
    starts_at: datetime,
    title: str,
) -> InterviewEvent:
    """Idempotently records an interview event."""
    stmt = select(InterviewEvent).where(
        InterviewEvent.application_id == application_id,
        InterviewEvent.starts_at == starts_at,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing

    event = InterviewEvent(
        tenant_id=tenant_id,
        application_id=application_id,
        title=title,
        starts_at=starts_at,
        reminder_24h_sent=False,
        reminder_1h_sent=False,
    )
    session.add(event)
    await session.flush()
    return event


async def list_interviews(
    session: AsyncSession,
    tenant_id: str,
) -> List[Dict[str, Any]]:
    """Lists upcoming and past interview events for a candidate."""
    stmt = (
        select(InterviewEvent)
        .options(selectinload(InterviewEvent.application))
        .where(InterviewEvent.tenant_id == tenant_id)
        .order_by(InterviewEvent.starts_at.asc())
    )
    res = await session.execute(stmt)
    events = res.scalars().all()

    return [
        {
            "id": e.id,
            "title": e.title,
            "starts_at": e.starts_at.isoformat(),
            "company_name": e.application.company_name if e.application else "Company",
            "job_title": e.application.job_title if e.application else "",
            "reminder_24h_sent": e.reminder_24h_sent,
            "reminder_1h_sent": e.reminder_1h_sent,
        }
        for e in events
    ]


async def run_due_reminders(
    session: AsyncSession,
    tenant_id: str,
    now: datetime,
) -> List[Dict[str, Any]]:
    """Evaluates due reminder windows and generates sent reminder messages."""
    stmt = (
        select(InterviewEvent)
        .options(selectinload(InterviewEvent.application))
        .where(
            InterviewEvent.tenant_id == tenant_id,
            InterviewEvent.starts_at > now,
        )
    )
    res = await session.execute(stmt)
    events = res.scalars().all()

    # Get candidate user email
    user_stmt = select(User).where(User.tenant_id == tenant_id).limit(1)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    recipient_email = user.email if user else "candidate@example.com"

    emitted: List[Dict[str, Any]] = []
    for evt in events:
        tokens = due_reminders(evt, now)
        for token in tokens:
            company = evt.application.company_name if evt.application else "Company"
            subject = f"Interview reminder: {evt.title} ({token} before)"
            body = (
                f"Reminder: You have an upcoming interview with {company} for {evt.title}.\n"
                f"Scheduled Time: {evt.starts_at.isoformat()}\n"
                f"Window: {token} before start."
            )
            msg = OutreachMessage(
                tenant_id=tenant_id,
                application_id=evt.application_id,
                recipient_name=user.email if user else "Candidate",
                recipient_email=recipient_email,
                recipient_role="Candidate",
                subject=subject,
                body_text=body,
                status="sent",
                sent_at=now,
            )
            session.add(msg)
            if token == "24h":
                evt.reminder_24h_sent = True
            elif token == "1h":
                evt.reminder_1h_sent = True

            emitted.append({
                "event_id": evt.id,
                "token": token,
                "subject": subject,
                "recipient": recipient_email,
            })

    await session.flush()
    return emitted
