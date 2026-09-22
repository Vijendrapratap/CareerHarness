from datetime import datetime, timedelta, timezone
import pytest

from app.domain.inbox import thread_for_application
from app.domain.models import ApplicationTrack, InboundEmail, JobListing, OutreachMessage, Tenant


@pytest.mark.asyncio
async def test_thread_for_application_sorts_and_isolates_tenant(db_session):
    tenant1 = Tenant(name="Tenant 1", plan="pro")
    tenant2 = Tenant(name="Tenant 2", plan="pro")
    job = JobListing(
        id="job-inbox-001",
        title="Software Engineer",
        company="Initech",
        url="https://initech.example/jobs/1",
        description="Engineering role",
    )
    db_session.add_all([tenant1, tenant2, job])
    await db_session.flush()

    app_track = ApplicationTrack(
        tenant_id=tenant1.id,
        job_id=job.id,
        company_name="Initech",
        job_title="Software Engineer",
        portal_type="greenhouse",
        status="applied",
    )
    db_session.add(app_track)
    await db_session.flush()

    t0 = datetime.now(timezone.utc) - timedelta(hours=2)
    t1 = datetime.now(timezone.utc) - timedelta(hours=1)

    out_msg = OutreachMessage(
        tenant_id=tenant1.id,
        application_id=app_track.id,
        recipient_name="Peter",
        recipient_email="peter@initech.com",
        subject="Application follow-up",
        body_text="Hi Peter, excited about the role.",
        status="sent",
        sent_at=t0,
        created_at=t0,
    )
    in_msg = InboundEmail(
        tenant_id=tenant1.id,
        application_id=app_track.id,
        sender_email="peter@initech.com",
        subject="Re: Application follow-up",
        body_text="Thanks for reaching out! Let's talk.",
        classification="interview",
        confidence_score=0.98,
        received_at=t1,
    )
    # Message for tenant2 on same application_id
    leak_msg = InboundEmail(
        tenant_id=tenant2.id,
        application_id=app_track.id,
        sender_email="spy@other.com",
        subject="Leak",
        body_text="Should not be seen.",
        classification="other",
        received_at=t1,
    )

    db_session.add_all([out_msg, in_msg, leak_msg])
    await db_session.flush()

    thread = await thread_for_application(db_session, tenant1.id, app_track.id)
    assert len(thread) == 2
    assert thread[0]["direction"] == "out"
    assert thread[0]["subject"] == "Application follow-up"
    assert thread[1]["direction"] == "in"
    assert thread[1]["subject"] == "Re: Application follow-up"
    assert all(m["subject"] != "Leak" for m in thread)
