"""Recruiter Conversation Inbox Domain Service (Task 11).

Aggregates outbound and inbound recruiter communication threads
per tracked application.
"""

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import ApplicationTrack, InboundEmail, OutreachMessage


async def thread_for_application(
    session: AsyncSession,
    tenant_id: str,
    application_id: str,
) -> List[Dict[str, Any]]:
    """Each item is {"direction": "out"|"in", "subject": str, "body": str, "at": str}."""
    # Outbound messages
    out_q = select(OutreachMessage).where(
        OutreachMessage.tenant_id == tenant_id,
        OutreachMessage.application_id == application_id,
    )
    out_msgs = (await session.execute(out_q)).scalars().all()

    # Inbound emails
    in_q = select(InboundEmail).where(
        InboundEmail.tenant_id == tenant_id,
        InboundEmail.application_id == application_id,
    )
    in_msgs = (await session.execute(in_q)).scalars().all()

    items: List[Dict[str, Any]] = []
    for m in out_msgs:
        ts = m.sent_at or m.created_at
        items.append({
            "direction": "out",
            "subject": m.subject,
            "body": m.body_text,
            "at": ts.isoformat() if ts else "",
            "_dt": ts,
        })

    for m in in_msgs:
        ts = m.received_at or m.created_at
        items.append({
            "direction": "in",
            "subject": m.subject,
            "body": m.body_text,
            "at": ts.isoformat() if ts else "",
            "_dt": ts,
        })

    items.sort(key=lambda x: x["_dt"])
    for item in items:
        item.pop("_dt", None)

    return items


async def list_recruiter_threads(
    session: AsyncSession,
    tenant_id: str,
) -> List[Dict[str, Any]]:
    """Groups conversation threads by application."""
    apps_q = (
        select(ApplicationTrack)
        .where(ApplicationTrack.tenant_id == tenant_id)
        .order_by(ApplicationTrack.last_activity_at.desc())
    )
    apps = (await session.execute(apps_q)).scalars().all()

    threads: List[Dict[str, Any]] = []
    for app in apps:
        messages = await thread_for_application(session, tenant_id, app.id)
        if messages:
            threads.append({
                "application_id": app.id,
                "company_name": app.company_name,
                "job_title": app.job_title,
                "messages": messages,
            })
    return threads
