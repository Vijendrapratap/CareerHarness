import pytest
from sqlalchemy import select

from app.domain.models import ApplicationTrack, JobListing, OutreachMessage, Tenant
from app.domain.recruiter_hunter import draft_recruiter_touch, extract_public_email


def test_extracts_a_posted_email_and_ignores_linkedin_urls():
    assert extract_public_email("Apply at jobs@acme.com or ignore us.") == "jobs@acme.com"
    assert extract_public_email("https://www.linkedin.com/in/someone") is None


@pytest.mark.asyncio
async def test_draft_recruiter_touch_no_email_leaves_zero_messages(db_session):
    tenant = Tenant(name="Hunter Tenant", plan="pro")
    job = JobListing(
        id="job-hunter-001",
        title="Engineer",
        company="Acme Corp",
        url="https://acme.example/jobs/1",
        description="No contact address here, just a description.",
    )
    db_session.add(tenant)
    db_session.add(job)
    await db_session.flush()

    app_track = ApplicationTrack(
        tenant_id=tenant.id,
        job_id=job.id,
        company_name="Acme Corp",
        job_title="Engineer",
        portal_type="greenhouse",
        status="applied",
    )
    db_session.add(app_track)
    await db_session.flush()

    res = await draft_recruiter_touch(
        session=db_session,
        tenant_id=tenant.id,
        application_id=app_track.id,
        job_text=job.description,
        resume_excerpt="Skilled engineer.",
        cover_letter="Dear Team, please consider my application.",
    )
    assert res["status"] == "no_public_email"

    count_q = select(OutreachMessage).where(OutreachMessage.tenant_id == tenant.id)
    msgs = (await db_session.execute(count_q)).scalars().all()
    assert len(msgs) == 0


@pytest.mark.asyncio
async def test_draft_recruiter_touch_with_email_creates_pending_approval(db_session):
    tenant = Tenant(name="Hunter Tenant 2", plan="pro")
    job = JobListing(
        id="job-hunter-002",
        title="Backend Engineer",
        company="Acme Corp",
        url="https://acme.example/jobs/2",
        description="Send resumes to hiring@acme.com for consideration.",
    )
    db_session.add(tenant)
    db_session.add(job)
    await db_session.flush()

    app_track = ApplicationTrack(
        tenant_id=tenant.id,
        job_id=job.id,
        company_name="Acme Corp",
        job_title="Backend Engineer",
        portal_type="greenhouse",
        status="applied",
    )
    db_session.add(app_track)
    await db_session.flush()

    res = await draft_recruiter_touch(
        session=db_session,
        tenant_id=tenant.id,
        application_id=app_track.id,
        job_text=job.description,
        resume_excerpt="Skilled engineer.",
        cover_letter="Dear Team, please consider my application.",
    )
    assert res["status"] == "pending_approval"
    assert res["recipient"] == "hiring@acme.com"

    count_q = select(OutreachMessage).where(OutreachMessage.tenant_id == tenant.id)
    msgs = (await db_session.execute(count_q)).scalars().all()
    assert len(msgs) == 1
    assert msgs[0].status == "pending_approval"
    assert msgs[0].recipient_email == "hiring@acme.com"
    assert msgs[0].recipient_role == "Recruiter"
