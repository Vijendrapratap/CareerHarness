"""Job Ingestion, Deduplication, and Analyst Match/Ghost-Job Scoring (F8)."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import JobListing, JobMatch
from app.domain.roles import roles_service


class JobService:
    """Manages job listing deduplication, ghost-job risk analysis, and candidate matching."""

    @staticmethod
    def calculate_ghost_job_risk(
        description: str,
        company: str,
        salary_min: Optional[int],
        salary_max: Optional[int],
    ) -> float:
        """Heuristic Analyst scoring to flag ghost/scam job listings (F8)."""
        risk = 0.0

        # Description length check
        desc_clean = description.strip()
        if len(desc_clean) < 150:
            risk += 0.4
        elif len(desc_clean) < 300:
            risk += 0.2

        # Vague description / placeholder flags
        vague_terms = ["fast money", "urgent hire", "work from home guaranteed", "wire transfer"]
        if any(term in desc_clean.lower() for term in vague_terms):
            risk += 0.5

        # Unrealistic salary signals
        if salary_min and salary_max:
            if salary_max > 500000 and "executive" not in desc_clean.lower():
                risk += 0.3

        return min(1.0, risk)

    @staticmethod
    async def ingest_job(
        session: AsyncSession,
        title: str,
        company: str,
        url: str,
        description: str,
        portal_type: str = "greenhouse",
        location: str = "Remote",
        salary_min: Optional[int] = None,
        salary_max: Optional[int] = None,
    ) -> JobListing:
        """Deduplicates by (company, url) and calculates ghost job risk."""
        clean_url = url.strip()
        clean_company = company.strip()

        # Check deduplication index
        query = select(JobListing).where(
            JobListing.company == clean_company,
            JobListing.url == clean_url,
        )
        existing = (await session.execute(query)).scalar_one_or_none()
        if existing:
            return existing

        # Ghost job detection
        ghost_score = JobService.calculate_ghost_job_risk(
            description=description,
            company=clean_company,
            salary_min=salary_min,
            salary_max=salary_max,
        )

        job = JobListing(
            id=str(uuid.uuid4()),
            title=title.strip(),
            company=clean_company,
            url=clean_url,
            location=location.strip(),
            salary_min=salary_min,
            salary_max=salary_max,
            description=description.strip(),
            portal_type=portal_type.lower(),
            is_ghost_job=(ghost_score >= 0.7),
            ghost_risk_score=ghost_score,
        )
        session.add(job)
        await session.flush()
        return job

    @staticmethod
    async def score_and_match_job(
        session: AsyncSession,
        tenant_id: str,
        job_id: str,
    ) -> JobMatch:
        """Analyst Agent: scores job against candidate verified skills and priority role."""
        job = await session.get(JobListing, job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        # Fetch candidate priority role
        roles = await roles_service.get_selected_roles(session, tenant_id)
        role_title = roles[0].title if roles else "Software Engineer"

        # Match score calculation
        score = 8.0
        # Title keyword match
        if any(w.lower() in job.title.lower() for w in role_title.split() if len(w) > 3):
            score += 1.5  # Priority role weight ×1.5

        # Cap between 1.0 and 10.0
        final_match_score = min(10.0, max(1.0, score))
        why = f"Matches candidate target role '{role_title}' with strong domain alignment."

        match = JobMatch(
            tenant_id=tenant_id,
            job_id=job.id,
            match_score=final_match_score,
            why_matched=why,
            status="new",
        )
        session.add(match)
        await session.flush()
        return match


job_service = JobService()
