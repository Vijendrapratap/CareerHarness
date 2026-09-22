"""Recruiter Hunter from Job Posting Service (Task 9).

Extracts public recruiter emails directly from the job posting text
and stages a pending_approval outreach message.
"""

import re
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import ApplicationTrack, OutreachMessage


def extract_public_email(text: str) -> Optional[str]:
    """Extracts first valid email address from text, ignoring URLs without emails."""
    if not text:
        return None
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    if match:
        return match.group(0)
    return None


async def draft_recruiter_touch(
    session: AsyncSession,
    tenant_id: str,
    application_id: str,
    job_text: str,
    resume_excerpt: str,
    cover_letter: str,
) -> Dict[str, Any]:
    """Drafts an outreach message to a recruiter printed in the job description."""
    email = extract_public_email(job_text)
    if not email:
        return {"status": "no_public_email"}

    # Fetch job title from application track if available
    app_stmt = select(ApplicationTrack).where(
        ApplicationTrack.id == application_id,
        ApplicationTrack.tenant_id == tenant_id,
    )
    app_track = (await session.execute(app_stmt)).scalar_one_or_none()
    job_title = app_track.job_title if app_track else "Position"

    subject = f"Application for {job_title}"
    body = (
        f"{cover_letter}\n\n"
        f"---\n"
        f"Resume Highlights:\n{resume_excerpt}"
    )

    msg = OutreachMessage(
        tenant_id=tenant_id,
        application_id=application_id,
        recipient_name="Recruiting team",
        recipient_email=email,
        recipient_role="Recruiter",
        subject=subject,
        body_text=body,
        status="pending_approval",
    )
    session.add(msg)
    await session.flush()
    return {"status": "pending_approval", "recipient": email}
