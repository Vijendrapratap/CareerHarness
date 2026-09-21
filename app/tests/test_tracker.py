"""Unit and contract tests for Tracker and Outreach Loop (F11).

Tests:
- GT-04: Outreach send rate cap enforced (strictly <= 15 emails/day).
- GT-05: Reply classifier categorizes correctly & silence >10d flags ghosted.
- CT-03: Outreach consent verified before first send.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Consent, JobListing, Tenant
from app.domain.tracker import (
    OutreachConsentMissingError,
    OutreachRateLimitExceededError,
    classify_inbound_email,
    create_outreach_draft,
    detect_silence_and_mark_ghosted,
    send_outreach_message,
    track_application,
)


def test_gt05_reply_classification_accuracy():
    """GT-05: Reply classifier correctly categorizes interview, assessment, rejection, request_info."""
    # 1. Interview invitation
    res_interview = classify_inbound_email(
        subject="Interview invitation: Senior Backend Engineer at Acme",
        body_text="We would love to schedule an interview with you. Please use this calendly.com/acme link to pick a time.",
    )
    assert res_interview["classification"] == "interview"
    assert res_interview["confidence"] >= 0.9

    # 2. Assessment
    res_assessment = classify_inbound_email(
        subject="Next steps - technical assessment",
        body_text="Please complete the following take-home coding challenge on HackerRank within 48 hours.",
    )
    assert res_assessment["classification"] == "assessment"

    # 3. Rejection
    res_rejection = classify_inbound_email(
        subject="Your application with CloudNet",
        body_text="Thank you for your time. Unfortunately, we are not moving forward with your candidacy as we pursue other candidates.",
    )
    assert res_rejection["classification"] == "rejection"

    # 4. Request Info
    res_info = classify_inbound_email(
        subject="Quick question regarding your application",
        body_text="Could you please confirm your salary expectation and earliest availability for this position?",
    )
    assert res_info["classification"] == "request_info"


@pytest.mark.asyncio
async def test_gt05_silence_detector_marks_ghosted(db_session: AsyncSession):
    """GT-05: Silence detector flags applications with >10 days of inactivity as ghosted."""
    tenant = Tenant(name="Tracker User", plan="free")
    job1 = JobListing(
        id="job-ghost-1",
        title="Software Engineer",
        company="Silent Corp",
        url="https://silentcorp.com/jobs/1",
    )
    job2 = JobListing(
        id="job-active-2",
        title="DevOps Engineer",
        company="Responsive Inc",
        url="https://responsive.com/jobs/2",
    )
    db_session.add(tenant)
    db_session.add(job1)
    db_session.add(job2)
    await db_session.flush()

    # Track app1 with silence of 12 days
    app1 = await track_application(db_session, tenant.id, job1, status="applied")
    app1.last_activity_at = datetime.now(timezone.utc) - timedelta(days=12)

    # Track app2 with recent activity (2 days ago)
    app2 = await track_application(db_session, tenant.id, job2, status="applied")
    app2.last_activity_at = datetime.now(timezone.utc) - timedelta(days=2)
    await db_session.flush()

    # Run detector
    ghosted = await detect_silence_and_mark_ghosted(db_session, tenant.id, days_threshold=10)
    assert len(ghosted) == 1
    assert ghosted[0].id == app1.id
    assert ghosted[0].is_ghosted is True
    assert ghosted[0].status == "ghosted"

    assert app2.is_ghosted is False
    assert app2.status == "applied"


@pytest.mark.asyncio
async def test_ct03_and_gt04_outreach_consent_and_daily_send_cap(db_session: AsyncSession):
    """CT-03 & GT-04: Enforces outreach consent check and strict daily send cap of <= 15 emails/day."""
    tenant = Tenant(name="Outreach User", plan="pro", trusted_mode=True)
    db_session.add(tenant)
    await db_session.flush()

    # 1. Without consent -> raises OutreachConsentMissingError (CT-03)
    draft1 = await create_outreach_draft(
        session=db_session,
        tenant_id=tenant.id,
        recipient_name="Sarah Connor",
        recipient_email="sconnor@acme.com",
        recipient_role="Engineering Director",
        company_name="Acme",
        job_title="Lead Architect",
        candidate_name="John Doe",
        pitch_bullets=["Architected event-driven microservices"],
    )

    with pytest.raises(OutreachConsentMissingError):
        await send_outreach_message(db_session, tenant.id, draft1.id)

    # 2. Grant email outreach consent (CT-03)
    consent = Consent(tenant_id=tenant.id, consent_type="email_connect")
    db_session.add(consent)
    await db_session.flush()

    # Now sending draft1 succeeds
    sent_msg = await send_outreach_message(db_session, tenant.id, draft1.id)
    assert sent_msg.status == "sent"
    assert sent_msg.sent_at is not None

    # 3. Simulate 14 more sent messages today (reaching 15)
    now = datetime.now(timezone.utc)
    for i in range(14):
        d = await create_outreach_draft(
            session=db_session,
            tenant_id=tenant.id,
            recipient_name=f"Manager {i}",
            recipient_email=f"mgr{i}@acme.com",
            recipient_role="Manager",
            company_name="Acme",
            job_title="Engineer",
            candidate_name="John Doe",
            pitch_bullets=[],
        )
        d.status = "sent"
        d.sent_at = now
        db_session.add(d)
    await db_session.flush()

    # 4. Attempting 16th email -> raises OutreachRateLimitExceededError (GT-04)
    draft16 = await create_outreach_draft(
        session=db_session,
        tenant_id=tenant.id,
        recipient_name="Alex 16",
        recipient_email="alex16@acme.com",
        recipient_role="Recruiter",
        company_name="Acme",
        job_title="Engineer",
        candidate_name="John Doe",
        pitch_bullets=[],
    )

    with pytest.raises(OutreachRateLimitExceededError) as exc_info:
        await send_outreach_message(db_session, tenant.id, draft16.id)

    assert "Daily outreach limit reached (15/15" in str(exc_info.value)
