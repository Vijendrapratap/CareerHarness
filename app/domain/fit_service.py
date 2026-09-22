"""Database glue for the fit engine: build the candidate snapshot, persist fits, rank fixes."""

from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.candidate_facts import get_facts
from app.domain.fit import APPLY_LINE, CandidateSnapshot, evaluate
from app.domain.models import JobFit, JobListing, JobMatch, ResumeParse
from app.domain.roles import roles_service


async def candidate_snapshot(session: AsyncSession, tenant_id: str) -> CandidateSnapshot:
    roles = await roles_service.get_selected_roles(session, tenant_id)
    resume = (await session.execute(
        select(ResumeParse).where(ResumeParse.tenant_id == tenant_id).order_by(ResumeParse.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    skills = resume.extracted_skills if resume else []
    facts = await get_facts(session, tenant_id)
    return CandidateSnapshot(
        role_titles=[r.title for r in roles],
        verified_skills={s["name"] for s in skills if s.get("verified")},
        resume_skills={s["name"] for s in skills if not s.get("verified")},
        declined_skills=set(facts.get("declined_skills") or []),
        facts=facts,
    )


async def evaluate_tenant(session: AsyncSession, tenant_id: str, job_ids: Optional[List[str]] = None) -> int:
    """(Re)scores the candidate's matched jobs. Cheap: no network, no LLM."""
    query = select(JobMatch).options(selectinload(JobMatch.job)).where(JobMatch.tenant_id == tenant_id)
    if job_ids is not None:
        query = query.where(JobMatch.job_id.in_(job_ids))
    matches = (await session.execute(query)).scalars().all()
    if not matches:
        return 0

    snap = await candidate_snapshot(session, tenant_id)
    existing = {
        f.job_id: f for f in (await session.execute(
            select(JobFit).where(JobFit.tenant_id == tenant_id, JobFit.job_id.in_([m.job_id for m in matches]))
        )).scalars().all()
    }
    for match in matches:
        job = match.job
        report = evaluate(job.title, job.company, job.location or "", job.description or "", snap)
        fit = existing.get(job.id)
        if fit is None:
            fit = JobFit(tenant_id=tenant_id, job_id=job.id, score=report.score, verdict=report.verdict)
            session.add(fit)
        fit.score, fit.verdict, fit.report = report.score, report.verdict, report.to_dict()
        match.match_score = report.score * 2  # JobMatch keeps its 0-10 scale (trusted mode uses 9.0)
        match.why_matched = (report.gates or report.strengths or report.gaps or [""])[0]
    await session.flush()
    return len(matches)


async def get_fit(session: AsyncSession, tenant_id: str, job_id: str) -> Optional[JobFit]:
    return (await session.execute(
        select(JobFit).where(JobFit.tenant_id == tenant_id, JobFit.job_id == job_id)
    )).scalar_one_or_none()


async def fix_impact(session: AsyncSession, tenant_id: str) -> List[Dict]:
    """Skill confirmations ranked by how many jobs they would lift over the apply line."""
    fits = (await session.execute(select(JobFit).where(JobFit.tenant_id == tenant_id))).scalars().all()
    impact: Dict[str, Dict] = {}
    for fit in fits:
        for fix in (fit.report or {}).get("fixes", []):
            row = impact.setdefault(fix["skill"], {
                "skill": fix["skill"], "in_resume": fix.get("in_resume", False),
                "jobs_unlocked": 0, "jobs_improved": 0, "total_gain": 0.0,
            })
            row["jobs_improved"] += 1
            row["total_gain"] += fix["gain"]
            if fit.score < APPLY_LINE <= round(fit.score + fix["gain"], 1):
                row["jobs_unlocked"] += 1
    # Skills already in the resume are far likelier to be true: suggest those first.
    ranked = sorted(impact.values(), key=lambda r: (-r["jobs_unlocked"], not r["in_resume"], -r["jobs_improved"]))
    for row in ranked:
        row["avg_gain"] = round(row.pop("total_gain") / row["jobs_improved"], 1)
    return ranked


async def apply_ready_count(session: AsyncSession, tenant_id: str) -> int:
    return len((await session.execute(
        select(JobFit.id).where(JobFit.tenant_id == tenant_id, JobFit.score >= APPLY_LINE)
    )).all())


class FitGateError(Exception):
    """Applying is refused: the job's fit is below the apply line."""


async def ensure_apply_line(session: AsyncSession, tenant_id: str, job: JobListing) -> float:
    """Returns the job's fit score, or raises FitGateError naming the gate or the biggest fix."""
    fit = await get_fit(session, tenant_id, job.id)
    if fit is not None:
        score, report = fit.score, fit.report or {}
    else:  # e.g. a job applied to directly, never scouted
        result = evaluate(job.title, job.company, job.location or "", job.description or "",
                          await candidate_snapshot(session, tenant_id))
        score, report = result.score, result.to_dict()
    if score >= APPLY_LINE:
        return score
    message = f"Fit {score}/5 is below the {APPLY_LINE} apply line."
    if report.get("gates"):
        message += f" Blocked: {report['gates'][0]}."
    elif report.get("fixes"):
        top = report["fixes"][0]
        message += f" Biggest fix: confirm {top['skill']} (+{top['gain']})."
    raise FitGateError(message)
