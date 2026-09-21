"""Integration tests for Phase 4 Tracker and Insights API routers."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.api.main import app
from app.domain.models import Consent, JobListing, ReadinessScore, Tenant


@pytest.mark.asyncio
async def test_tracker_and_insights_api_lifecycle(db_session):
    """Full API integration test for Tracking, Reply Classification, Outreach, Funnel Analytics, and Settings."""
    app.dependency_overrides[get_db] = lambda: db_session

    tenant = Tenant(name="P4 Full Test Tenant", plan="pro", trusted_mode=False)
    job = JobListing(
        id="job-p4-001",
        title="Senior Staff Engineer",
        company="Datadog",
        url="https://datadog.com/jobs/001",
        portal_type="greenhouse",
    )
    db_session.add(tenant)
    db_session.add(job)
    await db_session.flush()

    # Give tenant email consent
    consent = Consent(tenant_id=tenant.id, consent_type="email_connect")
    db_session.add(consent)
    await db_session.commit()

    headers = {"X-Tenant-ID": tenant.id}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Track Application
        track_req = {"job_id": job.id, "status": "applied"}
        res_track = await client.post("/api/tracker/track", json=track_req, headers=headers)
        assert res_track.status_code == 200
        app_data = res_track.json()
        assert app_data["company_name"] == "Datadog"
        app_id = app_data["id"]

        # 2. Process Inbound Email (Simulate Interview invite) (GT-05)
        email_req = {
            "sender_email": "recruiting@datadog.com",
            "subject": "Interview scheduling for Senior Staff Engineer",
            "body_text": "We would like to invite you for an interview. Pick a time on calendly.com/datadog",
            "application_id": app_id,
        }
        res_email = await client.post("/api/tracker/inbound-email", json=email_req, headers=headers)
        assert res_email.status_code == 200
        email_data = res_email.json()
        assert email_data["classification"] == "interview"

        # Verify application status was auto-advanced
        res_apps = await client.get("/api/tracker/applications", headers=headers)
        assert res_apps.status_code == 200
        apps_list = res_apps.json()
        assert len(apps_list) == 1
        assert apps_list[0]["status"] == "interview"

        # 3. Draft Outreach Message
        outreach_req = {
            "recipient_name": "Dave Director",
            "recipient_email": "dave@datadog.com",
            "recipient_role": "VP Engineering",
            "company_name": "Datadog",
            "job_title": "Senior Staff Engineer",
            "candidate_name": "Pat Engineer",
            "pitch_bullets": ["Scaled Datadog agent integrations"],
            "application_id": app_id,
        }
        res_draft = await client.post("/api/tracker/outreach/draft", json=outreach_req, headers=headers)
        assert res_draft.status_code == 200
        draft_data = res_draft.json()
        outreach_id = draft_data["id"]

        # 4. Send Outreach (Trusted mode is False -> Pending approval without bypass) (GT-01)
        res_send_gated = await client.post(
            f"/api/tracker/outreach/{outreach_id}/send",
            json={"bypass_approval": False},
            headers=headers,
        )
        assert res_send_gated.status_code == 200
        assert res_send_gated.json()["status"] == "pending_approval"

        # Send with approval bypass -> status becomes sent
        res_send_approved = await client.post(
            f"/api/tracker/outreach/{outreach_id}/send",
            json={"bypass_approval": True},
            headers=headers,
        )
        assert res_send_approved.status_code == 200
        assert res_send_approved.json()["status"] == "sent"

        # 5. Funnel Analytics API (BT-01)
        res_funnel = await client.get("/api/insights/funnel", headers=headers)
        assert res_funnel.status_code == 200
        funnel_data = res_funnel.json()["funnel"]
        assert funnel_data["total_applications"] == 1
        assert funnel_data["interviews"] == 1
        assert funnel_data["interview_rate_percent"] == 100.0

        # 6. Trusted Mode Gate: attempt to enable without readiness score -> 400 (BT-02)
        res_tm_fail = await client.post(
            "/api/insights/trusted-mode",
            json={"enable": True},
            headers=headers,
        )
        assert res_tm_fail.status_code == 400
        assert "Readiness score" in res_tm_fail.json()["detail"]

        # Add passing readiness score (88)
        readiness = ReadinessScore(
            tenant_id=tenant.id,
            overall_score=88,
            is_capped_at_69=False,
        )
        db_session.add(readiness)
        await db_session.commit()

        # Now enabling Trusted Mode succeeds
        res_tm_ok = await client.post(
            "/api/insights/trusted-mode",
            json={"enable": True},
            headers=headers,
        )
        assert res_tm_ok.status_code == 200
        assert res_tm_ok.json()["trusted_mode"] is True

        # 7. Update Cadence & Check Settings Summary (BT-03)
        res_cadence = await client.patch(
            "/api/insights/cadence",
            json={"cadence": "hourly"},
            headers=headers,
        )
        assert res_cadence.status_code == 200
        assert res_cadence.json()["cadence"] == "hourly"

        res_settings = await client.get("/api/insights/settings", headers=headers)
        assert res_settings.status_code == 200
        settings_data = res_settings.json()
        assert settings_data["trusted_mode"] is True
        assert settings_data["scout_cadence"] == "hourly"
        assert settings_data["readiness_score"] == 88

    app.dependency_overrides.clear()
