"""Integration test for Execution Engine API routers (Vault and Applications)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.api.main import app
from app.domain.models import JobFit, JobListing, Tenant


@pytest.mark.asyncio
async def test_execution_api_full_lifecycle(db_session):
    """End-to-end API test exercising Vault, Tailoring, ATS Check, Questions, Submit, and Lineage."""
    app.dependency_overrides[get_db] = lambda: db_session
    tenant = Tenant(name="API Execution Tenant", plan="pro")
    job = JobListing(
        id="job-api-exec-001",
        title="Senior Platform Engineer",
        company="Stripe",
        url="https://stripe.com/jobs/platform-001",
        description="Senior Platform Engineer needed. Must have Python, Docker, Kubernetes, and distributed systems experience.",
    )
    db_session.add(tenant)
    db_session.add(job)
    await db_session.flush()
    # Exercises the submission ladder, not fit scoring: seed a fit above the apply line.
    db_session.add(JobFit(tenant_id=tenant.id, job_id=job.id, score=4.5, verdict="apply", report={}))
    await db_session.commit()

    headers = {"X-Tenant-ID": tenant.id}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Master Resume in Vault
        master_payload = {
            "title": "Master Resume - Engineering",
            "content": {
                "candidate_name": "Alex Smith",
                "skills": ["Python", "Docker", "PostgreSQL", "Kubernetes"],
                "experience": [
                    {
                        "company": "Cloud Corp",
                        "dates": "2020 - 2024",
                        "bullets": [
                            "Deployed Kubernetes clusters managing 500+ microservices",
                            "Wrote core Python infrastructure processing 10M daily events",
                        ],
                    }
                ],
                "education": [
                    {"school": "MIT", "degree": "BS", "year": "2020"}
                ],
            },
            "raw_markdown": "# Alex Smith Resume",
        }
        res_master = await client.post("/api/vault/master", json=master_payload, headers=headers)
        assert res_master.status_code == 200
        master_data = res_master.json()
        assert master_data["is_master"] is True
        master_id = master_data["id"]

        # 2. Tailor Resume for Stripe job
        tailor_req = {
            "job_id": job.id,
            "parent_version_id": master_id,
            "save_to_vault": True,
        }
        res_tailor = await client.post("/api/applications/tailor", json=tailor_req, headers=headers)
        assert res_tailor.status_code == 200
        tailor_data = res_tailor.json()
        assert tailor_data["honesty_review"]["is_honest"] is True
        tailored_version_id = tailor_data["vault_version_id"]
        assert tailored_version_id is not None

        # 3. Check ATS Compatibility
        ats_req = {
            "job_id": job.id,
            "tailored_content": tailor_data["tailored_resume"],
        }
        res_ats = await client.post("/api/applications/ats-check", json=ats_req, headers=headers)
        assert res_ats.status_code == 200
        ats_data = res_ats.json()
        assert ats_data["passed"] is True
        assert ats_data["overall_ats_score"] >= 60

        # 4. Screening Questions
        questions_req = {
            "questions": [
                "Are you legally authorized to work in the United States?",
                "Do you have experience with Python?",
                "Do you hold a Top Secret Security Clearance?",
            ]
        }
        res_sq = await client.post("/api/applications/screening-questions", json=questions_req, headers=headers)
        assert res_sq.status_code == 200
        sq_data = res_sq.json()
        assert sq_data["requires_hitl"] is True  # Because Top Secret is unverified!
        assert len(sq_data["unanswered_questions"]) == 1

        # 5. Submit Application (Bot block -> Fallback to Tier 3 Handoff)
        submit_req = {
            "job_id": job.id,
            "resume_version_id": tailored_version_id,
            "screening_answers": sq_data["answers"],
            "simulate_bot_block": True,
            "has_connected_email": False,
        }
        res_submit = await client.post("/api/applications/submit", json=submit_req, headers=headers)
        assert res_submit.status_code == 200
        submit_data = res_submit.json()
        assert submit_data["bot_mitigation_tier"] == 3
        assert submit_data["channel"] == "candidate_handoff"
        assert submit_data["status"] == "handoff_ready"

        # 6. Audit logs endpoint
        res_audit = await client.get("/api/applications/audit-logs", headers=headers)
        assert res_audit.status_code == 200
        logs = res_audit.json()
        assert len(logs) == 1
        assert logs[0]["bot_mitigation_tier"] == 3

        # 7. Immutability check: modifying document returns 400
        res_mutate = await client.put(f"/api/vault/versions/{tailored_version_id}", headers=headers)
        assert res_mutate.status_code == 400
        assert "immutable" in res_mutate.json()["detail"]

        # 8. Promote tailored branch to new Master
        promote_req = {"version_id": tailored_version_id}
        res_promote = await client.post("/api/vault/promote", json=promote_req, headers=headers)
        assert res_promote.status_code == 200
        promoted_data = res_promote.json()
        assert promoted_data["is_master"] is True
        assert promoted_data["parent_id"] == tailored_version_id

        # 9. Lineage tree
        res_lineage = await client.get("/api/vault/lineage", headers=headers)
        assert res_lineage.status_code == 200
        tree = res_lineage.json()
        assert len(tree) >= 1

    app.dependency_overrides.clear()
