"""Tests for Scout Scheduling & Rate-Limiting meeting RD-02 and RD-03 specifications."""

import pytest

from app.domain.models import ReadinessScore
from app.domain.scout import ScoutRateLimitError, scout_scheduler


@pytest.fixture
async def cleared_readiness_tenant(db_session, sample_tenant):
    """Sets up a tenant that has passed the Readiness Gate (score >= 70, 0 criticals)."""
    score = ReadinessScore(
        tenant_id=sample_tenant.id,
        overall_score=85,
        ats_parse_score=15,
        metric_coverage_score=20,
        honest_keyword_score=15,
        linkedin_headline_about_score=20,
        experience_mirroring_score=15,
        critical_todos_cleared_score=15,
        is_capped_at_69=False,
    )
    db_session.add(score)
    await db_session.commit()
    return sample_tenant


@pytest.mark.asyncio
async def test_rd02_passing_score_auto_schedules_scout(db_session, cleared_readiness_tenant):
    """RD-02: Passing readiness score auto-schedules Scout execution."""
    schedule = await scout_scheduler.auto_schedule_on_gate_pass(
        session=db_session,
        tenant_id=cleared_readiness_tenant.id,
    )

    assert schedule.is_active is True
    assert schedule.cadence in ("daily", "hourly")


@pytest.mark.asyncio
async def test_rd03_manual_scan_rate_limits(db_session, cleared_readiness_tenant, second_tenant):
    """RD-03: Manual scan is rate-limited to 3/day for Free and 10/day for Pro."""
    # 1. Test Free plan (second_tenant is "free")
    free_score = ReadinessScore(
        tenant_id=second_tenant.id,
        overall_score=80,
        critical_todos_cleared_score=15,
        is_capped_at_69=False,
    )
    db_session.add(free_score)
    await db_session.commit()

    # Free plan allows exactly 3 manual scans
    for _ in range(3):
        res = await scout_scheduler.trigger_manual_scan(db_session, second_tenant.id)
        assert res["status"] == "scout_started"

    # 4th scan must raise ScoutRateLimitError
    with pytest.raises(ScoutRateLimitError) as exc_info:
        await scout_scheduler.trigger_manual_scan(db_session, second_tenant.id)
    assert "3/day on Free" in str(exc_info.value)

    # 2. Test Pro plan (cleared_readiness_tenant is "pro")
    # Pro allows up to 10 scans
    for i in range(10):
        res = await scout_scheduler.trigger_manual_scan(db_session, cleared_readiness_tenant.id)
        assert res["scans_used"] == (i + 1)

    # 11th scan raises limit error
    with pytest.raises(ScoutRateLimitError) as exc_info_pro:
        await scout_scheduler.trigger_manual_scan(db_session, cleared_readiness_tenant.id)
    assert "10/day on Pro" in str(exc_info_pro.value)
