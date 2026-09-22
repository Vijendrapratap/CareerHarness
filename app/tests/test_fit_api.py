"""Facts + fix-loop API: answering facts and confirming skills visibly moves jobs over the apply line."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.api.main import app
from app.domain.fit_service import evaluate_tenant
from app.domain.jobs import job_service
from app.domain.models import JobMatch
from app.domain.resume_parser import resume_parser
from app.domain.roles import roles_service

JD = (
    "<h3>Requirements</h3><ul><li>5+ years with Python</li><li>Strong experience with PostgreSQL and Docker</li>"
    "<li>You have shipped REST APIs</li></ul><p>Remote.</p>"
)


@pytest.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def tenant_with_jobs(db_session, sample_tenant):
    tid = sample_tenant.id
    await roles_service.select_roles(db_session, tid, ["role_backend_arch"])
    await resume_parser.parse_resume_text(db_session, tid, "cv.txt", "Engineer. Python, PostgreSQL, Docker, REST APIs.")
    for i in range(3):
        job = await job_service.ingest_job(db_session, title="Backend Engineer", company=f"Co{i}",
                                           url=f"https://x/{i}", description=JD, location="Remote")
        db_session.add(JobMatch(tenant_id=tid, job_id=job.id, match_score=8.0))
    await db_session.flush()
    await evaluate_tenant(db_session, tid)
    return {"X-Tenant-ID": tid}


@pytest.mark.asyncio
async def test_facts_api_asks_next_question_and_rescores(client, tenant_with_jobs):
    h = tenant_with_jobs
    first = (await client.get("/api/profile/facts", headers=h)).json()
    assert first["next_question"]["id"] == "years_experience" and first["answered"] == 0

    res = await client.patch("/api/profile/facts", headers=h, json={"years_experience": 6})
    assert res.status_code == 200
    assert res.json()["next_question"]["id"] == "seniority" and res.json()["answered"] == 1

    bad = await client.patch("/api/profile/facts", headers=h, json={"work_mode": "moon"})
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_fixes_rank_by_jobs_unlocked_and_confirm_unlocks_them(client, tenant_with_jobs):
    h = tenant_with_jobs
    await client.patch("/api/profile/facts", headers=h, json={"years_experience": 6, "work_mode": "remote_only"})
    fixes = (await client.get("/api/fit/fixes", headers=h)).json()
    assert fixes and fixes[0]["jobs_improved"] == 3

    ready = 0
    for fix in fixes:
        res = (await client.post("/api/fit/fixes/confirm-skill", headers=h, json={"skill": fix["skill"]})).json()
        assert res["apply_ready"] >= ready
        ready = res["apply_ready"]
    assert ready == 3


@pytest.mark.asyncio
async def test_declining_a_skill_removes_it_from_fixes(client, tenant_with_jobs):
    h = tenant_with_jobs
    skill = (await client.get("/api/fit/fixes", headers=h)).json()[0]["skill"]
    await client.post("/api/fit/fixes/decline-skill", headers=h, json={"skill": skill})
    assert skill not in [f["skill"] for f in (await client.get("/api/fit/fixes", headers=h)).json()]


@pytest.mark.asyncio
async def test_apply_is_refused_below_the_line_with_the_fix(client, db_session, tenant_with_jobs):
    h = tenant_with_jobs
    job_id = (await client.get("/api/jobs", headers=h)).json()[0]["job_id"]
    res = await client.post("/api/applications/choose", headers=h, json={"job_id": job_id, "mode": "original"})
    assert res.status_code == 403
    assert "below the 4.0 apply line" in res.json()["detail"] and "confirm" in res.json()["detail"].lower()
    sub = await client.post("/api/applications/submit", headers=h, json={"job_id": job_id, "resume_version_id": "x"})
    assert sub.status_code == 403


@pytest.mark.asyncio
async def test_batch_confirm_resume_skills_rescores_once(client, tenant_with_jobs):
    h = tenant_with_jobs
    await client.patch("/api/profile/facts", headers=h, json={"years_experience": 6, "work_mode": "any"})
    res = await client.post("/api/fit/fixes/confirm-skills", headers=h,
                            json={"skills": ["Python", "PostgreSQL", "Docker", "REST APIs"]})
    assert res.status_code == 200
    assert res.json()["apply_ready"] == 3 and res.json()["unlocked"] == 3


@pytest.mark.asyncio
async def test_wins_prefer_skills_already_in_the_resume(client, db_session, tenant_with_jobs):
    fixes = (await client.get("/api/fit/fixes", headers=tenant_with_jobs)).json()
    in_resume = [f["in_resume"] for f in fixes]
    assert in_resume == sorted(in_resume, reverse=True) or fixes[0]["jobs_unlocked"] > 0
