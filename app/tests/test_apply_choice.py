import pytest

from app.domain.apply_choice import prepare_application
from app.domain.models import JobFit, JobListing, Tenant
from app.domain.vault import create_initial_master


@pytest.mark.asyncio
async def test_apply_choice_original_and_refine(db_session):
    tenant = Tenant(name="Apply Choice Tenant", plan="pro")
    db_session.add(tenant)
    await db_session.flush()

    master_content = {
        "candidate_name": "Ada Lovelace",
        "skills": ["Python", "Algorithms", "Mathematics"],
        "experience": [
            {
                "company": "Babbage Labs",
                "dates": "1840 - 1850",
                "bullets": [
                    "Wrote the first computer algorithm for the Analytical Engine",
                ],
            }
        ],
        "education": [{"school": "Self-taught", "degree": "Pioneer", "year": "1840"}],
    }

    master = await create_initial_master(
        session=db_session,
        tenant_id=tenant.id,
        title="Master Resume",
        content=master_content,
        raw_markdown="# Master Resume",
    )

    job = JobListing(
        id="job-choice-001",
        title="Senior Algorithm Engineer",
        company="Engine Corp",
        url="https://engine.example/jobs/1",
        description="Senior Algorithm Engineer needed with Python and mathematics expertise.",
    )
    db_session.add(job)
    # This test is about packet preparation, not fit: seed a fit above the apply line.
    db_session.add(JobFit(tenant_id=tenant.id, job_id=job.id, score=4.5, verdict="apply", report={}))
    await db_session.flush()

    # 1. Mode: original
    res_orig = await prepare_application(
        session=db_session,
        tenant_id=tenant.id,
        job_id=job.id,
        mode="original",
    )
    assert res_orig["mode"] == "original"
    assert res_orig["draft_source"] == "original"
    assert res_orig["resume_version_id"] == master.id
    bullets = res_orig["resume_content"]["experience"][0]["bullets"]
    assert "Wrote the first computer algorithm for the Analytical Engine" in bullets

    # 2. Mode: refine
    res_refine = await prepare_application(
        session=db_session,
        tenant_id=tenant.id,
        job_id=job.id,
        mode="refine",
    )
    assert res_refine["mode"] == "refine"
    assert res_refine["draft_source"] == "deterministic"
    assert res_refine["honesty_review"]["is_honest"] is True
    assert res_refine["resume_version_id"] is not None
