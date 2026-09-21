"""Tests for LinkedIn Intake & Consent Tracking meeting LI-01 and CT-04 specifications."""

import pytest
from sqlalchemy import select

from app.domain.linkedin import ConsentRequiredError, LinkedInFetchError, linkedin_service
from app.domain.models import Consent, LinkedInProfile


@pytest.mark.asyncio
async def test_ct04_consent_timestamp_stored_before_fetch(db_session, sample_tenant):
    """CT-04: Explicit consent must precede any external fetch action, with timestamp recorded."""
    url = "https://www.linkedin.com/in/candidate-public"

    # 1. Fetching without consent is rejected immediately
    with pytest.raises(ConsentRequiredError):
        await linkedin_service.fetch_public_profile(
            session=db_session,
            tenant_id=sample_tenant.id,
            public_url=url,
            user_consented=False,
        )

    # 2. With consent, a Consent record is persisted
    profile = await linkedin_service.fetch_public_profile(
        session=db_session,
        tenant_id=sample_tenant.id,
        public_url=url,
        user_consented=True,
        ip_address="192.168.1.50",
    )
    assert profile.source_mode == "url_fetch"

    # Verify consent record
    consent_record = (
        await db_session.execute(
            select(Consent).where(
                Consent.tenant_id == sample_tenant.id,
                Consent.consent_type == "linkedin_fetch",
            )
        )
    ).scalar_one()
    assert consent_record.granted_at is not None
    assert consent_record.ip_address == "192.168.1.50"


@pytest.mark.asyncio
async def test_li01_fetch_failure_triggers_seamless_paste_fallback(db_session, sample_tenant):
    """LI-01: Remote fetch failure (login-wall/429) triggers graceful paste fallback."""
    # 1. Fetch failure
    with pytest.raises(LinkedInFetchError) as exc_info:
        await linkedin_service.fetch_public_profile(
            session=db_session,
            tenant_id=sample_tenant.id,
            public_url="https://www.linkedin.com/in/rate-limited-profile",
            user_consented=True,
            simulate_fetch_failure=True,
        )
    assert "paste" in str(exc_info.value).lower()

    # 2. Seamlessly submit via paste-as-text mode
    pasted = await linkedin_service.save_profile_paste(
        session=db_session,
        tenant_id=sample_tenant.id,
        headline="Staff Distributed Systems Engineer | ex-Google",
        about="Specializing in large-scale event-driven platforms and fault-tolerant storage.",
        skills=["Python", "Go", "Kafka", "PostgreSQL"],
    )

    assert pasted.source_mode == "paste"
    assert "Staff Distributed Systems" in pasted.headline

    # Verify stored in DB
    db_profile = (
        await db_session.execute(
            select(LinkedInProfile).where(LinkedInProfile.tenant_id == sample_tenant.id)
        )
    ).scalar_one()
    assert db_profile.source_mode == "paste"
