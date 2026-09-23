"""Apply sessions: gated start, fill -> answer -> approve, memory across jobs, dry-run and daily cap.

The browser is stubbed here (see test_apply_browser.py for real fills against fixture forms).
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.api.main import app
from app.apply.answers import question_key
from app.apply.browser import FillResult
from app.core.config import settings
from app.domain import apply_sessions
from app.domain.apply_sessions import process_session
from app.domain.candidate_facts import get_facts
from app.domain.models import ApplicationTrack, ApplySession, JobFit, JobListing, ResumeFile

WHY = "Why do you want to work at Acme?"


@pytest.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def ready_job(db_session, sample_tenant, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "APPLY_ARTIFACT_DIR", str(tmp_path))
    tid = sample_tenant.id
    jobs = []
    run = uuid.uuid4().hex[:8]  # endpoints commit, so rows outlive a test: keep URLs unique
    for url in ([f"https://jobs.ashbyhq.com/acme/{run}-1", f"https://jobs.ashbyhq.com/acme/{run}-2"]):
        job = JobListing(title="Backend Engineer", company="Acme", url=url, description="x")
        db_session.add(job)
        await db_session.flush()
        db_session.add(JobFit(tenant_id=tid, job_id=job.id, score=4.4, verdict="apply", report={}))
        jobs.append(job)
    db_session.add(ResumeFile(tenant_id=tid, filename="cv.pdf", content=b"%PDF-1.4 cv"))
    await db_session.flush()
    return tid, jobs


def stub_browser(monkeypatch, calls):
    async def fake_run_fill(url, ctx, submit=False, screenshot_path=""):
        calls.append({"url": url, "submit": submit, "memory": dict(ctx.memory), "resume": ctx.resume_path})
        if question_key(WHY) not in ctx.memory:
            return FillResult("needs_answers", [{"label": "Email", "value": "a@b.c", "source": "profile"}],
                              [{"key": "3", "label": WHY, "kind": "textarea", "options": [], "required": True}])
        if submit:
            return FillResult("submitted", [], [], message="Application submitted.")
        return FillResult("ready", [], [], message="Everything is filled in.")

    monkeypatch.setattr(apply_sessions, "run_fill", fake_run_fill)


@pytest.mark.asyncio
async def test_full_flow_answer_once_then_approve(client, db_session, ready_job, monkeypatch):
    tid, (job, second) = ready_job
    h = {"X-Tenant-ID": tid}
    calls = []
    stub_browser(monkeypatch, calls)
    monkeypatch.setattr(settings, "APPLY_SUBMIT_ENABLED", True)

    res = await client.post("/api/apply/sessions", headers=h, json={"job_id": job.id, "mode": "original"})
    assert res.status_code == 202
    sid = res.json()["id"]
    assert res.json()["ats"] == "ashby" and res.json()["apply_url"].endswith("/application")

    await process_session(db_session, sid, submit=False)
    body = (await client.get(f"/api/apply/sessions/{sid}", headers=h)).json()
    assert body["status"] == "needs_answers" and body["questions"][0]["label"] == WHY
    assert calls[0]["resume"].endswith("cv.pdf")  # the candidate's own file

    assert (await client.post(f"/api/apply/sessions/{sid}/approve", headers=h)).status_code == 409

    res = await client.post(f"/api/apply/sessions/{sid}/answers", headers=h,
                            json={"answers": {WHY: "I love the product."}, "profile": {"phone": "+44 1"}})
    assert res.status_code == 200
    facts = await get_facts(db_session, tid)
    assert facts["apply_answers"][question_key(WHY)] == "I love the product."
    assert facts["apply_profile"]["phone"] == "+44 1"

    await process_session(db_session, sid, submit=False)
    assert (await client.get(f"/api/apply/sessions/{sid}", headers=h)).json()["status"] == "ready"

    assert (await client.post(f"/api/apply/sessions/{sid}/approve", headers=h)).status_code == 202
    await process_session(db_session, sid, submit=True)
    body = (await client.get(f"/api/apply/sessions/{sid}", headers=h)).json()
    assert body["status"] == "submitted"
    track = (await db_session.execute(select(ApplicationTrack).where(ApplicationTrack.job_id == job.id))).scalar_one()
    assert track.status == "applied"

    # The next application reuses the remembered answer: no question this time.
    sid2 = (await client.post("/api/apply/sessions", headers=h, json={"job_id": second.id, "mode": "original"})).json()["id"]
    await process_session(db_session, sid2, submit=False)
    assert (await client.get(f"/api/apply/sessions/{sid2}", headers=h)).json()["status"] == "ready"


@pytest.mark.asyncio
async def test_submission_disabled_means_dry_run(client, db_session, ready_job, monkeypatch):
    tid, (job, _) = ready_job
    calls = []
    stub_browser(monkeypatch, calls)
    monkeypatch.setattr(settings, "APPLY_SUBMIT_ENABLED", False)
    s = ApplySession(tenant_id=tid, job_id=job.id, ats="ashby", apply_url="https://jobs.ashbyhq.com/acme/1/application",
                     status="submitting")
    db_session.add(s)
    await db_session.flush()
    from app.domain.candidate_facts import update_facts
    await update_facts(db_session, tid, {"apply_answers": {question_key(WHY): "Because."}})
    await process_session(db_session, s.id, submit=True)
    assert s.status == "dry_run" and calls[-1]["submit"] is False


@pytest.mark.asyncio
async def test_gates_unsupported_site_and_daily_cap(client, db_session, ready_job, monkeypatch):
    tid, (job, _) = ready_job
    h = {"X-Tenant-ID": tid}
    run = uuid.uuid4().hex[:8]
    low = JobListing(title="Backend Engineer", company="Low", url=f"https://jobs.ashbyhq.com/low/{run}", description="x")
    other = JobListing(title="Backend Engineer", company="Board", url=f"https://remoteok.com/remote-jobs/{run}", description="x")
    db_session.add_all([low, other])
    await db_session.flush()
    db_session.add_all([JobFit(tenant_id=tid, job_id=low.id, score=3.1, verdict="skip", report={}),
                        JobFit(tenant_id=tid, job_id=other.id, score=4.5, verdict="apply", report={})])
    await db_session.flush()

    assert (await client.post("/api/apply/sessions", headers=h, json={"job_id": low.id})).status_code == 403
    handoff = (await client.post("/api/apply/sessions", headers=h, json={"job_id": other.id})).json()
    assert handoff["status"] == "handoff" and handoff["apply_url"] == other.url

    monkeypatch.setattr(settings, "APPLY_DAILY_CAP", 1)
    db_session.add(ApplySession(tenant_id=tid, job_id=job.id, status="submitted"))
    ready = ApplySession(tenant_id=tid, job_id=job.id, status="ready")
    db_session.add(ready)
    await db_session.flush()
    assert (await client.post(f"/api/apply/sessions/{ready.id}/approve", headers=h)).status_code == 429
