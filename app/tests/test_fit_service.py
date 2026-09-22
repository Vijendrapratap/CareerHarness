"""Fits are persisted per job, recomputed when the candidate changes, and exposed on /api/jobs."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.api.main import app
from app.domain.candidate_facts import update_facts
from app.domain.fit_service import evaluate_tenant, get_fit
from app.domain.jobs import job_service
from app.domain.models import JobMatch
from app.domain.resume_parser import resume_parser, verify_skill
from app.domain.roles import roles_service

JD = (
    "<h3>What you have</h3><ul><li>5+ years building backend services in Python</li>"
    "<li>Strong experience with PostgreSQL and Docker</li><li>You have shipped REST APIs</li></ul>"
    "<p>Remote.</p>"
)


@pytest.fixture
async def candidate_with_job(db_session, sample_tenant):
    tid = sample_tenant.id
    await roles_service.select_roles(db_session, tid, ["role_backend_arch"])
    await resume_parser.parse_resume_text(
        db_session, tid, "cv.txt", "Backend engineer. Python, PostgreSQL, Docker, REST APIs. Cut latency 40%."
    )
    await update_facts(db_session, tid, {"years_experience": 6, "work_mode": "remote_only"})
    job = await job_service.ingest_job(db_session, title="Backend Engineer", company="Acme",
                                       url="https://x/1", description=JD, location="Remote")
    db_session.add(JobMatch(tenant_id=tid, job_id=job.id, match_score=8.0, why_matched="title"))
    await db_session.flush()
    return tid, job


@pytest.mark.asyncio
async def test_confirming_skills_raises_the_fit_and_match_score(db_session, candidate_with_job):
    tid, job = candidate_with_job
    assert await evaluate_tenant(db_session, tid) == 1
    before = await get_fit(db_session, tid, job.id)
    before_score = before.score
    assert before.verdict in ("stretch", "skip")  # skills only in resume text, unconfirmed

    for skill in ("Python", "PostgreSQL", "Docker", "REST APIs"):
        await verify_skill(db_session, tid, skill)
    await evaluate_tenant(db_session, tid)
    after = await get_fit(db_session, tid, job.id)
    assert after.score > before_score and after.verdict == "apply"
    match = (await db_session.execute(select(JobMatch).where(JobMatch.job_id == job.id))).scalar_one()
    assert match.match_score == after.score * 2


@pytest.mark.asyncio
async def test_jobs_api_includes_fit(db_session, candidate_with_job):
    tid, job = candidate_with_job
    await evaluate_tenant(db_session, tid)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            rows = (await c.get("/api/jobs", headers={"X-Tenant-ID": tid})).json()
    finally:
        app.dependency_overrides.clear()
    fit = rows[0]["fit"]
    assert fit["verdict"] in ("apply", "stretch", "skip")
    assert {r["skill"] for r in fit["requirements"]} >= {"Python", "PostgreSQL"}
    assert fit["fixes"] and fit["fixes"][0]["kind"] == "confirm_skill"
    assert rows[0]["location"] == "Remote"
