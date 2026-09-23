"""Apply sessions: start (gated), fill in a browser, collect answers, approve, submit or hand off."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.apply.answers import ApplyContext, question_key
from app.apply.browser import resolve_apply_url, run_fill
from app.core.config import settings
from app.domain.candidate_facts import get_facts, update_facts
from app.domain.fit_service import ensure_apply_line
from app.domain.models import (
    ApplicationTrack,
    ApplySession,
    DocumentVersion,
    JobListing,
    ResumeFile,
    Tenant,
    User,
)


class ApplyError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def session_dict(s: ApplySession) -> Dict[str, Any]:
    return {
        "id": s.id, "job_id": s.job_id, "mode": s.mode, "ats": s.ats, "apply_url": s.apply_url,
        "status": s.status, "fields": s.fields or [], "questions": s.questions or [],
        "message": s.message, "has_screenshot": bool(s.screenshot_path),
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _greenhouse_org(company: str, facts: Dict[str, Any]) -> Optional[str]:
    from app.domain.scout import DEFAULT_BOARDS

    for b in DEFAULT_BOARDS:
        if b["portal"] == "greenhouse" and b.get("name", "").lower() == company.lower():
            return b["org"]
    board = (facts.get("company_boards") or {}).get(company)
    return board.split(":", 1)[1] if board and board.startswith("greenhouse:") else None


async def start_session(db: AsyncSession, tenant_id: str, job_id: str, mode: str = "original",
                        resume_version_id: Optional[str] = None) -> ApplySession:
    job = await db.get(JobListing, job_id)
    if job is None:
        raise ApplyError("Job not found.", 404)
    from app.domain.fit_service import FitGateError

    try:
        await ensure_apply_line(db, tenant_id, job)
    except FitGateError as exc:
        raise ApplyError(str(exc), 403) from exc

    resolved = resolve_apply_url(job.url, _greenhouse_org(job.company, await get_facts(db, tenant_id)))
    s = ApplySession(tenant_id=tenant_id, job_id=job.id, mode=mode, resume_version_id=resume_version_id)
    if resolved is None:
        s.status, s.apply_url = "handoff", job.url
        s.message = "This job applies on the company's own site. Open it to apply — auto-fill supports Greenhouse, Lever and Ashby."
    else:
        s.ats, s.apply_url, s.status = resolved[0], resolved[1], "filling"
    db.add(s)
    await db.flush()
    return s


async def _resume_file(db: AsyncSession, s: ApplySession, folder: Path) -> Optional[str]:
    if s.mode == "refine" and s.resume_version_id:
        version = await db.get(DocumentVersion, s.resume_version_id)
        if version and version.tenant_id == s.tenant_id:
            from app.domain.pdf_generator import AtsPdfGenerator

            path = folder / "resume-tailored.pdf"
            path.write_bytes(AtsPdfGenerator.generate_resume_pdf(version.content or {}))
            return str(path)
    original = (await db.execute(
        select(ResumeFile).where(ResumeFile.tenant_id == s.tenant_id).order_by(ResumeFile.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if original is None:
        return None
    path = folder / Path(original.filename).name
    path.write_bytes(original.content)
    return str(path)


async def _context(db: AsyncSession, s: ApplySession, folder: Path) -> ApplyContext:
    facts = await get_facts(db, s.tenant_id)
    tenant = await db.get(Tenant, s.tenant_id)
    user = (await db.execute(select(User).where(User.tenant_id == s.tenant_id).limit(1))).scalar_one_or_none()
    profile = {"full_name": tenant.name if tenant else "", "email": user.email if user else "",
               "location": (facts.get("locations") or [""])[0]}
    profile.update(facts.get("apply_profile") or {})
    return ApplyContext(profile=profile, facts=facts, memory=dict(facts.get("apply_answers") or {}),
                        resume_path=await _resume_file(db, s, folder))


async def _record_submission(db: AsyncSession, s: ApplySession) -> None:
    job = await db.get(JobListing, s.job_id)
    exists = (await db.execute(select(ApplicationTrack).where(
        ApplicationTrack.tenant_id == s.tenant_id, ApplicationTrack.job_id == s.job_id))).scalar_one_or_none()
    if job and not exists:
        db.add(ApplicationTrack(tenant_id=s.tenant_id, job_id=job.id, resume_version_id=s.resume_version_id,
                                company_name=job.company, job_title=job.title, portal_type=job.portal_type,
                                status="applied"))
    from app.domain.journey import note_application_submitted

    await note_application_submitted(db, s.tenant_id)


async def process_session(db: AsyncSession, session_id: str, submit: bool) -> ApplySession:
    """Fill (and with submit=True and submission enabled, submit) one session. Browser first, writes after."""
    s = await db.get(ApplySession, session_id)
    if s is None or s.status in ("handoff", "submitted"):
        return s
    folder = Path(settings.APPLY_ARTIFACT_DIR) / s.id
    folder.mkdir(parents=True, exist_ok=True)
    ctx = await _context(db, s, folder)
    if ctx.resume_path is None:
        s.status, s.message = "failed", "Upload your resume in Counsel first."
        await db.flush()
        return s
    really_submit = submit and settings.APPLY_SUBMIT_ENABLED
    try:
        result = await run_fill(s.apply_url, ctx, submit=really_submit, screenshot_path=str(folder / "form.png"))
    except Exception as exc:  # network, timeouts, a site change
        s.status, s.message = "failed", f"Auto-fill could not finish ({type(exc).__name__}). Open the application to apply directly."
        await db.flush()
        return s

    s.fields, s.questions, s.message = result.fields, result.questions, result.message
    s.screenshot_path = str(folder / "form.png") if (folder / "form.png").exists() else ""
    s.status = result.status
    if submit and not settings.APPLY_SUBMIT_ENABLED and result.status == "ready":
        s.status = "dry_run"
        s.message = "Filled and checked. Submitting is switched off on this server, so nothing was sent."
    if s.status == "submitted":
        await _record_submission(db, s)
    await db.flush()
    return s


async def fill_in_background(session_id: str, submit: bool = False) -> None:
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        await process_session(db, session_id, submit)
        await db.commit()


async def save_answers(db: AsyncSession, s: ApplySession, answers: Dict[str, Any], profile: Dict[str, str]) -> None:
    facts = await get_facts(db, s.tenant_id)
    remembered = dict(facts.get("apply_answers") or {})
    remembered.update({question_key(label): value for label, value in answers.items() if value not in ("", None, [])})
    contact = {**(facts.get("apply_profile") or {}), **{k: v for k, v in profile.items() if v}}
    await update_facts(db, s.tenant_id, {"apply_answers": remembered, "apply_profile": contact})
    s.status, s.message = "filling", "Re-filling with your answers..."
    await db.flush()


async def approve(db: AsyncSession, s: ApplySession) -> None:
    if s.status != "ready":
        raise ApplyError("Answer the remaining questions first; approve once everything is filled.", 409)
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = (await db.execute(select(func.count(ApplySession.id)).where(
        ApplySession.tenant_id == s.tenant_id, ApplySession.status == "submitted",
        ApplySession.updated_at >= start_of_day))).scalar_one()
    if sent_today >= settings.APPLY_DAILY_CAP:
        raise ApplyError(f"Daily limit reached ({settings.APPLY_DAILY_CAP} applications). Try again tomorrow.", 429)
    s.status, s.message = "submitting", "Submitting..."
    await db.flush()
