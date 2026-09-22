from datetime import datetime, timedelta, timezone
import pytest

from app.domain.calendar import due_reminders, record_interview
from app.domain.models import ApplicationTrack, JobListing, Tenant


def test_reminder_windows():
    class Event:
        starts_at = datetime(2026, 10, 2, 15, 0, tzinfo=timezone.utc)
        reminder_24h_sent = False
        reminder_1h_sent = False

    early = Event.starts_at - timedelta(hours=30)
    day_before = Event.starts_at - timedelta(hours=20)
    hour_before = Event.starts_at - timedelta(minutes=30)

    e1 = Event()
    assert due_reminders(e1, early) == []
    assert due_reminders(e1, day_before) == ["24h"]
    assert due_reminders(e1, hour_before) == ["24h", "1h"]

    e1.reminder_24h_sent = True
    assert due_reminders(e1, hour_before) == ["1h"]


@pytest.mark.asyncio
async def test_record_interview_persists_and_is_idempotent(db_session):
    tenant = Tenant(name="Calendar Tenant", plan="pro")
    job = JobListing(
        id="job-cal-001",
        title="Staff Engineer",
        company="Stripe",
        url="https://stripe.example/jobs/1",
        description="Role",
    )
    db_session.add_all([tenant, job])
    await db_session.flush()

    app_track = ApplicationTrack(
        tenant_id=tenant.id,
        job_id=job.id,
        company_name="Stripe",
        job_title="Staff Engineer",
        portal_type="greenhouse",
        status="interview",
    )
    db_session.add(app_track)
    await db_session.flush()

    interview_time = datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc)

    # First call persists row
    evt1 = await record_interview(
        session=db_session,
        tenant_id=tenant.id,
        application_id=app_track.id,
        starts_at=interview_time,
        title="Technical Screen with Hiring Manager",
    )
    assert evt1.id is not None
    assert evt1.starts_at == interview_time

    # Second call returns same row ID (idempotent)
    evt2 = await record_interview(
        session=db_session,
        tenant_id=tenant.id,
        application_id=app_track.id,
        starts_at=interview_time,
        title="Technical Screen with Hiring Manager",
    )
    assert evt2.id == evt1.id
