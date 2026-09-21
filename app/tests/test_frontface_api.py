"""Integration tests for Phase 1 Front-Face First API routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.api.main import app


@pytest.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_frontface_complete_api_pipeline(client, sample_tenant):
    """Verifies complete end-to-end API pipeline from role selection to readiness check."""
    headers = {"X-Tenant-ID": sample_tenant.id}

    # 1. Check Catalog
    cat_res = await client.get("/api/roles/catalog", headers=headers)
    assert cat_res.status_code == 200
    catalog = cat_res.json()
    assert len(catalog) >= 5

    # 2. Select Roles (Backend Architect priority)
    role_res = await client.post(
        "/api/roles",
        headers=headers,
        json={
            "role_ids": ["role_backend_arch", "role_fullstack_eng"],
            "priority_role_id": "role_backend_arch",
        },
    )
    assert role_res.status_code == 201
    roles = role_res.json()
    assert len(roles) == 2
    assert roles[0]["rank"] == 1

    # 3. Upload Resume
    resume_payload = {
        "filename": "candidate_cv.txt",
        "content": (
            "Senior Backend Architect with 10 years experience.\n"
            "- Architected high-throughput message streaming cluster handling 10M events/day.\n"
            "- Managed PostgreSQL sharding and Redis caching clusters.\n"
            "Skills: Python, SQL, Distributed Systems, Redis."
        ),
    }
    res_res = await client.post("/api/resumes/upload", headers=headers, json=resume_payload)
    assert res_res.status_code == 201
    resume_data = res_res.json()
    resume_id = resume_data["id"]

    # 4. Confirm Skill (AT-06)
    confirm_res = await client.post(
        f"/api/resumes/{resume_id}/skills/Python/confirm",
        headers=headers,
    )
    assert confirm_res.status_code == 200
    python_entry = next(
        s for s in confirm_res.json()["extracted_skills"] if s["name"] == "Python"
    )
    assert python_entry["verified"] is True

    # 5. Paste LinkedIn Profile (F4)
    li_payload = {
        "headline": "Backend Architect | Distributed Systems",
        "about": "Passionate about highly resilient distributed backends.",
        "skills": ["Distributed Systems", "SQL", "Python"],
    }
    li_res = await client.post("/api/linkedin/paste", headers=headers, json=li_payload)
    assert li_res.status_code == 201

    # 6. Compute Gaps & Score (F5)
    gap_res = await client.post("/api/gaps/compute", headers=headers)
    assert gap_res.status_code == 200
    gap_data = gap_res.json()
    assert "overall_score" in gap_data

    # 7. List To-Do items (UX-09)
    todos_res = await client.get("/api/todos", headers=headers)
    assert todos_res.status_code == 200
    todos = todos_res.json()
    assert isinstance(todos, list)

    # 8. Check Readiness Gate (F7)
    readiness_res = await client.get("/api/readiness", headers=headers)
    assert readiness_res.status_code == 200
    readiness = readiness_res.json()
    assert "is_ready" in readiness
    assert "overall_score" in readiness
