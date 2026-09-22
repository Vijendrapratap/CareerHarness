"""Regression tests for the onboarding flow: counsel -> todos -> mailbox -> hunt."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import desc, select

from app.api.deps import get_db
from app.api.main import app
from app.domain.gap_engine import gap_engine
from app.domain.journey import get_or_create_journey, set_stage
from app.domain.models import ProfileSection, ResumeParse
from app.domain.resume_parser import resume_parser
from app.domain.roles import roles_service


@pytest.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_finalize_is_safe_after_candidate_moved_past_hunt(client, db_session, sample_tenant):
    await set_stage(db_session, sample_tenant.id, "active")
    res = await client.post("/api/counsel/finalize", headers={"X-Tenant-ID": sample_tenant.id})
    assert res.status_code == 200
    assert (await get_or_create_journey(db_session, sample_tenant.id)).stage == "active"


@pytest.mark.asyncio
async def test_stage_endpoint_rejects_skipping_stages(client, db_session, sample_tenant):
    res = await client.post(
        "/api/journey/stage", headers={"X-Tenant-ID": sample_tenant.id}, json={"stage": "hunt"}
    )
    assert res.status_code == 409
    assert (await get_or_create_journey(db_session, sample_tenant.id)).stage == "counsel"


@pytest.mark.asyncio
async def test_stage_endpoint_allows_next_stage(client, db_session, sample_tenant):
    await set_stage(db_session, sample_tenant.id, "mailbox")
    res = await client.post(
        "/api/journey/stage", headers={"X-Tenant-ID": sample_tenant.id}, json={"stage": "hunt"}
    )
    assert res.status_code == 200
    assert res.json()["stage"] == "hunt"


@pytest.mark.asyncio
async def test_chat_does_not_write_malformed_profile_sections(client, db_session, sample_tenant, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")  # no network in tests
    res = await client.post(
        "/api/counsel/chat",
        headers={"X-Tenant-ID": sample_tenant.id},
        json={"message": "I want to lead a team, remote please", "context": {"skills": ["Python"]}},
    )
    assert res.status_code == 200
    assert res.json()["detected_attributes"]["management"] is True
    rows = (
        await db_session.execute(select(ProfileSection).where(ProfileSection.tenant_id == sample_tenant.id))
    ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_accepting_skill_todo_verifies_the_skill(db_session, sample_tenant):
    await roles_service.select_roles(db_session, sample_tenant.id, ["role_ai_engineer"])
    await resume_parser.parse_resume_text(
        db_session, sample_tenant.id, "cv.txt", "AI engineer. Python and PyTorch work on LLMs, 40% faster evals."
    )
    _, todos, before = await gap_engine.compute_gaps(db_session, sample_tenant.id)
    skill_todo = next(t for t in todos if t.category == "skill_alignment" and "'Python'" in t.issue_text)

    _, after = await gap_engine.resolve_todo(db_session, sample_tenant.id, skill_todo.id, "accept")

    resume = (
        await db_session.execute(
            select(ResumeParse).where(ResumeParse.tenant_id == sample_tenant.id).order_by(desc(ResumeParse.created_at))
        )
    ).scalars().first()
    assert {"name": "Python", "verified": True} in [
        {"name": s["name"], "verified": s["verified"]} for s in resume.extracted_skills
    ]
    assert after.honest_keyword_score > before.honest_keyword_score


@pytest.mark.asyncio
async def test_full_onboarding_flow_reaches_hunt_without_mailbox(client, sample_tenant):
    h = {"X-Tenant-ID": sample_tenant.id}
    resume = (
        "Staff Backend Engineer\n"
        "- Cut p99 latency 40% on a Python REST APIs gateway serving 2M requests/day.\n"
        "- Moved 12 services to Docker, saving $30k per year in infra spend.\n"
        "- Led SQL schema redesign across 5 teams, improving query speed 3x.\n"
        "Skills: Python, JavaScript, SQL, Git, REST APIs, Docker"
    )
    assert (await client.post("/api/resumes/upload", headers=h, json={"filename": "cv.txt", "content": resume})).status_code == 201
    assert (await client.post("/api/counsel/answer", headers=h, json={"step": "resume", "text": "cv"})).status_code == 200
    assert (await client.post("/api/linkedin/paste", headers=h, json={"headline": "Full Stack Engineer | Python"})).status_code == 201
    assert (await client.post("/api/counsel/answer", headers=h, json={"step": "linkedin", "text": "headline"})).status_code == 200
    for step, text in [("target_work", "role_fullstack_eng"), ("priority_role", "role_fullstack_eng")]:
        assert (await client.post("/api/counsel/answer", headers=h, json={"step": step, "text": text})).status_code == 200
    roles = await client.post("/api/roles", headers=h, json={"role_ids": ["role_fullstack_eng"], "priority_role_id": "role_fullstack_eng"})
    assert [r["role_id"] for r in roles.json()] == ["role_fullstack_eng"]
    prefs = {"work_arrangement": "Remote Only", "authorization": "Authorized", "management": False, "dealbreakers": [], "preferences": "Prefers Remote Only"}
    assert (await client.post("/api/counsel/preferences", headers=h, json=prefs)).status_code == 200
    assert (await client.post("/api/counsel/finalize", headers=h)).json()["stage"] == "hunt"
    assert (await client.get("/api/counsel", headers=h)).json()["done"] is True

    await client.post("/api/gaps/compute", headers=h)
    for todo in (await client.get("/api/todos", headers=h)).json():
        if todo["status"] == "open":
            assert (await client.post(f"/api/todos/{todo['id']}", headers=h, json={"action": "accept"})).status_code == 200
    readiness = (await client.get("/api/readiness", headers=h)).json()
    assert readiness["is_ready"], readiness
    assert (await client.get("/api/journey", headers=h)).json()["stage"] == "hunt"
