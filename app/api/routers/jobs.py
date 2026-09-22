"""Job Ingestion & Matching API Router (F8)."""

from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_tenant_id
from app.domain.jobs import job_service
from app.domain.models import JobFit, JobListing, JobMatch

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


class JobIngestRequest(BaseModel):
    title: str
    company: str
    url: str
    description: str
    portal_type: str = "greenhouse"
    location: str = "Remote"
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_job(
    req: JobIngestRequest,
    session: AsyncSession = Depends(get_db),
):
    """Ingests and deduplicates a scouted job listing with ghost-job scoring."""
    job = await job_service.ingest_job(
        session=session,
        title=req.title,
        company=req.company,
        url=req.url,
        description=req.description,
        portal_type=req.portal_type,
        location=req.location,
        salary_min=req.salary_min,
        salary_max=req.salary_max,
    )
    await session.commit()
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "is_ghost_job": job.is_ghost_job,
        "ghost_risk_score": job.ghost_risk_score,
    }


@router.get("")
async def list_matched_jobs(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Returns candidate matched jobs, best fit first, with the fit report (score /5, gates, fixes)."""
    query = (
        select(JobMatch)
        .options(selectinload(JobMatch.job))
        .where(JobMatch.tenant_id == tenant_id)
        .order_by(JobMatch.match_score.desc())
    )
    records = (await session.execute(query)).scalars().all()
    fits = {
        f.job_id: f.report
        for f in (await session.execute(select(JobFit).where(JobFit.tenant_id == tenant_id))).scalars().all()
    }
    return [
        {
            "match_id": m.id,
            "job_id": m.job_id,
            "title": m.job.title if m.job else "Untitled Position",
            "company": m.job.company if m.job else "Unknown Company",
            "location": m.job.location if m.job else "",
            "url": m.job.url if m.job else "",
            "match_score": m.match_score,
            "why_matched": m.why_matched,
            "status": m.status,
            "fit": fits.get(m.job_id),
        }
        for m in records
    ]
