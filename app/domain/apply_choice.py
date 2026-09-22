"""Apply Choice Service (Task 8).

Prepares application packets using either the original master resume
or a tailored/refined resume with strict honesty gate enforcement.
"""

import json
from typing import Any, Dict, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keyvault import KeyInactiveError, KeyNotFoundError, key_vault
from app.domain.application_engine import (
    draft_application_packet,
    generate_cover_letter,
    review_tailored_honesty,
)
from app.domain.fit_service import ensure_apply_line
from app.domain.models import JobListing
from app.domain.vault import create_tailored_version, get_master_version


async def prepare_application(
    session: AsyncSession,
    tenant_id: str,
    job_id: str,
    mode: Literal["original", "refine"],
    save: bool = True,
) -> Dict[str, Any]:
    """Returns mode, resume_version_id, resume_content, cover_letter, honesty_review, draft_source."""
    if mode not in ("original", "refine"):
        raise ValueError("mode must be original or refine")

    # 1. Fetch Job
    job = (
        await session.execute(select(JobListing).where(JobListing.id == job_id))
    ).scalar_one_or_none()
    if not job:
        raise ValueError(f"JobListing with id '{job_id}' not found.")

    # Only jobs at or above the apply line can be applied to (skipped fixes keep the score honest).
    await ensure_apply_line(session, tenant_id, job)

    # 2. Fetch Master Resume
    master = await get_master_version(session, tenant_id, "resume")
    if not master:
        raise ValueError("No master resume found. Please upload or set a master resume first.")

    master_content = master.content
    verified_skills = master_content.get("skills", [])

    if mode == "original":
        cover = generate_cover_letter(master_content, job, master_content)
        honesty = review_tailored_honesty(master_content, master_content, verified_skills)
        return {
            "mode": "original",
            "resume_version_id": master.id,
            "resume_content": master_content,
            "cover_letter": cover,
            "honesty_review": honesty,
            "draft_source": "original",
        }

    # mode == "refine"
    raw_key = None
    try:
        raw_key = await key_vault.get_decrypted_key(session, tenant_id, "openrouter")
    except (KeyNotFoundError, KeyInactiveError):
        raw_key = None

    packet = await draft_application_packet(
        tenant_id=tenant_id,
        master_content=master_content,
        job=job,
        verified_skills=verified_skills,
        raw_key=raw_key,
        provider="openrouter",
    )

    tailored_resume = packet["tailored_resume"]
    resume_version_id = None
    if save:
        tailored_doc = await create_tailored_version(
            session=session,
            tenant_id=tenant_id,
            parent_version_id=master.id,
            target_job_id=job.id,
            target_role_id=None,
            title=f"Tailored: {job.company} - {job.title}",
            content=tailored_resume,
            raw_markdown=json.dumps(tailored_resume),
            document_type="resume",
        )
        resume_version_id = tailored_doc.id

    return {
        "mode": "refine",
        "resume_version_id": resume_version_id,
        "resume_content": tailored_resume,
        "cover_letter": packet["cover_letter"],
        "honesty_review": packet["honesty_review"],
        "draft_source": packet["draft_source"],
    }
