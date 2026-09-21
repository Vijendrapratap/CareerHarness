"""Unit and contract tests for Insights and Settings (F12).

Tests:
- BT-01: Funnel metrics & conversion rate calculations.
- BT-02: Trusted Mode toggle gate (score >= 70 + 0 criticals).
- BT-03: Settings management (cadence, email disconnect, profile).
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.insights import (
    PlanUpgradeRequiredError,
    ReadinessGateNotMetError,
    disconnect_mailbox,
    get_funnel_analytics,
    get_settings_summary,
    toggle_trusted_mode,
    update_scout_cadence,
)
from app.domain.models import (
    ConnectedEmail,
    DocumentVersion,
    JobListing,
    ReadinessScore,
    Tenant,
    TodoItem,
)
from app.domain.tracker import track_application


@pytest.mark.asyncio
async def test_bt01_funnel_analytics_calculations(db_session: AsyncSession):
    """BT-01: Aggregated funnel analytics compute correct conversion rates and breakdowns."""
    tenant = Tenant(name="Analytics User", plan="pro")
    db_session.add(tenant)
    await db_session.flush()

    # Ingest jobs with different portals
    j_gh = JobListing(id="j-gh", title="Dev", company="A", url="http://a", portal_type="greenhouse")
    j_lv = JobListing(id="j-lv", title="Dev", company="B", url="http://b", portal_type="lever")
    j_wd = JobListing(id="j-wd", title="Dev", company="C", url="http://c", portal_type="workday")
    j_dr = JobListing(id="j-dr", title="Dev", company="D", url="http://d", portal_type="direct")
    db_session.add_all([j_gh, j_lv, j_wd, j_dr])

    # Create master and tailored version
    doc_v1 = DocumentVersion(
        tenant_id=tenant.id,
        version_number=1,
        title="Master Resume",
        is_master=True,
        applications_count=4,
        interviews_count=1,
    )
    db_session.add(doc_v1)
    await db_session.flush()

    # Track 4 applications:
    # 1 interview on greenhouse
    # 1 assessment on lever
    # 1 rejection on workday
    # 1 ghosted on direct
    await track_application(db_session, tenant.id, j_gh, resume_version_id=doc_v1.id, status="interview")
    await track_application(db_session, tenant.id, j_lv, resume_version_id=doc_v1.id, status="assessment")
    await track_application(db_session, tenant.id, j_wd, resume_version_id=doc_v1.id, status="rejected")
    app4 = await track_application(db_session, tenant.id, j_dr, resume_version_id=doc_v1.id, status="ghosted")
    app4.is_ghosted = True
    await db_session.flush()

    analytics = await get_funnel_analytics(db_session, tenant.id)
    funnel = analytics["funnel"]

    assert funnel["total_applications"] == 4
    assert funnel["interviews"] == 1
    assert funnel["assessments"] == 1
    assert funnel["rejections"] == 1
    assert funnel["ghosted"] == 1
    assert funnel["response_rate_percent"] == 75.0  # (1 + 1 + 1) / 4 = 75%
    assert funnel["interview_rate_percent"] == 25.0  # 1 / 4 = 25%
    assert funnel["ghost_rate_percent"] == 25.0

    # Verify portal breakdown
    portals = analytics["by_portal_type"]
    assert "greenhouse" in portals
    assert portals["greenhouse"]["interviews"] == 1
    assert portals["workday"]["rejections"] == 1

    # Verify resume version breakdown
    versions = analytics["by_resume_version"]
    assert len(versions) == 1
    assert versions[0]["interview_rate"] == 25.0


@pytest.mark.asyncio
async def test_bt02_trusted_mode_gate_validation(db_session: AsyncSession):
    """BT-02: Tenant cannot enable Trusted Mode without passing readiness score >= 70 and 0 criticals."""
    tenant = Tenant(name="Trusted Mode Gate User", plan="pro", trusted_mode=False)
    db_session.add(tenant)
    await db_session.flush()

    # 1. Without any score -> raises ReadinessGateNotMetError
    with pytest.raises(ReadinessGateNotMetError):
        await toggle_trusted_mode(db_session, tenant.id, enable=True)

    # 2. Score below 70 (e.g. 65) -> raises ReadinessGateNotMetError
    score_low = ReadinessScore(
        tenant_id=tenant.id,
        overall_score=65,
        is_capped_at_69=False,
    )
    db_session.add(score_low)
    await db_session.flush()

    with pytest.raises(ReadinessGateNotMetError):
        await toggle_trusted_mode(db_session, tenant.id, enable=True)

    # 3. Score = 85, but 1 open critical todo remains -> raises ReadinessGateNotMetError
    score_high = ReadinessScore(
        tenant_id=tenant.id,
        overall_score=85,
        is_capped_at_69=False,
    )
    todo_crit = TodoItem(
        tenant_id=tenant.id,
        category="presentation",
        severity="critical",
        issue_text="Missing core metrics",
        why_it_matters="ATS reject",
        fix_draft="Draft",
        status="open",
    )
    db_session.add(score_high)
    db_session.add(todo_crit)
    await db_session.flush()

    with pytest.raises(ReadinessGateNotMetError) as exc_info:
        await toggle_trusted_mode(db_session, tenant.id, enable=True)
    assert "critical front-face items remain open" in str(exc_info.value)

    # 4. Resolve the critical todo -> Trusted mode enables successfully
    todo_crit.status = "accepted"
    await db_session.flush()

    updated_tenant = await toggle_trusted_mode(db_session, tenant.id, enable=True)
    assert updated_tenant.trusted_mode is True


@pytest.mark.asyncio
async def test_bt03_settings_cadence_and_mailbox_lifecycle(db_session: AsyncSession):
    """BT-03: Full settings lifecycle: Scout cadence, plan upgrade checks, and email disconnect."""
    # Free plan tenant
    tenant_free = Tenant(name="Free User", plan="free", trusted_mode=False)
    db_session.add(tenant_free)
    await db_session.flush()

    # Free plan can set daily cadence
    sched = await update_scout_cadence(db_session, tenant_free.id, "daily")
    assert sched.cadence == "daily"

    # Free plan attempting hourly cadence raises PlanUpgradeRequiredError
    with pytest.raises(PlanUpgradeRequiredError):
        await update_scout_cadence(db_session, tenant_free.id, "hourly")

    # Upgrade to Pro
    tenant_free.plan = "pro"
    await db_session.flush()
    sched_hourly = await update_scout_cadence(db_session, tenant_free.id, "hourly")
    assert sched_hourly.cadence == "hourly"

    # Connect mailbox and disconnect
    mb = ConnectedEmail(
        tenant_id=tenant_free.id,
        provider="gmail",
        email_address="user@gmail.com",
        access_token_encrypted="enc_tok",
        refresh_token_encrypted="enc_ref",
        token_expires_at=datetime.now(timezone.utc),
    )
    db_session.add(mb)
    await db_session.flush()

    summary = await get_settings_summary(db_session, tenant_free.id)
    assert summary["connected_email"] == "user@gmail.com"
    assert summary["scout_cadence"] == "hourly"

    # Disconnect mailbox
    disconnected = await disconnect_mailbox(db_session, tenant_free.id)
    assert disconnected is True

    summary_after = await get_settings_summary(db_session, tenant_free.id)
    assert summary_after["connected_email"] is None
