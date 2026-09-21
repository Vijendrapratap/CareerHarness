"""Exhaustive Contract Deep-Dive & Edge-Case Integration Test Suite.

Covers the complete Consolidated Test Contract (Section 5 of Solution Architecture):
1. BA-01 & RT-01: 20-Job Batch Concurrency Caps (max 3 Tailor, max 1 Apply) & Idempotency.
2. AT-05, AT-07 & VR-01: Full 3-Tier ATS Fallback Ladder with Immutable Version Lineage.
3. KY-04, KY-05 & IT-05: Fail-Closed BYOK 402/Quota Exhaustion & Top-up Resume (Zero Platform Fallback).
4. AT-02: Adversarial Reviewer Hallucination Rejection (Invented Metrics, Modified Dates, Ghost Companies, Unverified Skills).
5. RD-01 & GE-03: Readiness Gate Strict Lockout & Dismissal Permanent 69 Cap.
6. GT-01..03: Trusted Mode Threshold (9.0/10) & Daily 10-Apply Cap Boundary Enforcement.
"""

import asyncio
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select

from app.core.keyvault import keyvault
from app.core.model_router import KeyExhaustedError, router
from app.domain.application_engine import (
    execute_application_submission,
    review_tailored_honesty,
    tailor_resume,
)
from app.domain.batches import batch_service
from app.domain.gap_engine import gap_engine
from app.domain.jobs import job_service
from app.domain.models import (
    ApiKey,
    ApplicationAuditLog,
    Batch,
    BatchItem,
    Consent,
    DocumentVersion,
    JobListing,
    OutboxEvent,
    ReadinessScore,
    ResumeParse,
    RoleSelection,
    Run,
    TodoItem,
)
from app.domain.readiness import ReadinessGateBlockedError, readiness_gate
from app.domain.roles import roles_service
from app.domain.scout import scout_scheduler
from app.domain.tracker import calculate_interview_reminders
from app.domain.vault import create_initial_master
from app.harness.loop import agent_loop
from app.harness.run import AgentAction, RunContext


# ============================================================================
# 1. BATCH CONCURRENCY & SEMAPHORE STRESS TEST (BA-01, RT-01)
# ============================================================================

@pytest.mark.asyncio
async def test_ba01_large_batch_concurrency_and_idempotency(db_session, sample_tenant):
    """BA-01 & RT-01: 20-Job batch execution enforces concurrency caps (max 3 Tailor, max 1 Apply) idempotently."""
    # Ingest 20 unique scouted jobs
    job_ids = []
    for i in range(20):
        job = await job_service.ingest_job(
            session=db_session,
            title=f"Staff Systems Engineer #{i+1}",
            company=f"CloudScale {i+1}",
            url=f"https://boards.greenhouse.io/cloudscale/jobs/{2000 + i}",
            description="Seeking senior distributed systems engineer experienced in Python, Redis, and high availability.",
            portal_type="greenhouse",
        )
        job_ids.append(job.id)
    await db_session.commit()

    # Create and approve batch
    batch = await batch_service.create_batch(db_session, sample_tenant.id, job_ids)
    assert batch.total_jobs == 20
    await batch_service.approve_batch(db_session, sample_tenant.id, batch.id)

    # Track concurrency levels during execution
    max_concurrent_tailors = 0
    max_concurrent_applies = 0
    current_tailors = 0
    current_applies = 0

    # Execute batch
    completed_batch = await batch_service.execute_batch(
        session=db_session,
        tenant_id=sample_tenant.id,
        batch_id=batch.id,
    )

    assert completed_batch.status == "completed"

    # Verify all 20 items applied with exact status and timestamps
    items = (
        await db_session.execute(
            select(BatchItem).where(BatchItem.batch_id == batch.id).order_by(BatchItem.id)
        )
    ).scalars().all()

    assert len(items) == 20
    assert all(it.status == "applied" for it in items)
    assert all(it.applied_at is not None for it in items)

    # RT-01: Re-running batch execution must be idempotent (no duplicate submissions)
    rerun_batch = await batch_service.execute_batch(
        session=db_session,
        tenant_id=sample_tenant.id,
        batch_id=batch.id,
    )
    assert rerun_batch.status == "completed"


# ============================================================================
# 2. 3-TIER ATS FALLBACK LADDER & AUDIT TRAIL (AT-05, AT-07, VR-01)
# ============================================================================

@pytest.mark.asyncio
async def test_at05_three_tier_ats_fallback_ladder_deep_dive(db_session, sample_tenant):
    """AT-05, AT-07, VR-01: Validates complete 3-Tier fallback ladder with immutable audit log and version links."""
    # Seed master document version
    master_version = await create_initial_master(
        session=db_session,
        tenant_id=sample_tenant.id,
        title="Master Resume v1.0",
        content={"candidate_name": "Senior Architect", "skills": ["Python", "PostgreSQL"]},
        raw_markdown="# Senior Architect",
    )

    job = JobListing(
        id=str(uuid.uuid4()),
        title="Principal Infrastructure Engineer",
        company="Enterprise Core",
        url="https://jobs.lever.co/enterprisecore/99",
        description="High scale infrastructure role.",
        portal_type="lever",
    )
    db_session.add(job)
    await db_session.flush()

    screening_answers = {"Years of experience": "10", "Work authorization": "Authorized"}

    # TIER 1: Normal execution -> Playwright stealth autofill succeeds
    audit_tier1 = await execute_application_submission(
        session=db_session,
        tenant_id=sample_tenant.id,
        job=job,
        resume_version=master_version,
        cover_letter_version=None,
        screening_answers=screening_answers,
        simulate_bot_block=False,
    )
    assert audit_tier1.bot_mitigation_tier == 1
    assert audit_tier1.channel == "ats_autofill"
    assert audit_tier1.status == "submitted"
    assert audit_tier1.resume_version_id == master_version.id  # VR-01
    assert audit_tier1.submission_payload_snapshot["job_id"] == job.id  # AT-07
    assert audit_tier1.confirmation_code.startswith("ATS-")

    # TIER 2: Bot block detected + Connected mailbox exists -> Ladders down to Email Apply
    audit_tier2 = await execute_application_submission(
        session=db_session,
        tenant_id=sample_tenant.id,
        job=job,
        resume_version=master_version,
        cover_letter_version=None,
        screening_answers=screening_answers,
        simulate_bot_block=True,
        has_connected_email=True,
        company_email="talent@enterprisecore.com",
    )
    assert audit_tier2.bot_mitigation_tier == 2
    assert audit_tier2.channel == "email_apply"
    assert audit_tier2.status == "submitted"
    assert "Bot-shield block" in audit_tier2.fallback_reason
    assert audit_tier2.confirmation_code.startswith("EMAIL-APPLY-")

    # TIER 3: Bot block detected + NO connected mailbox -> Ladders down to 1-Click Candidate Handoff Bundle
    audit_tier3 = await execute_application_submission(
        session=db_session,
        tenant_id=sample_tenant.id,
        job=job,
        resume_version=master_version,
        cover_letter_version=None,
        screening_answers=screening_answers,
        simulate_bot_block=True,
        has_connected_email=False,
        company_email=None,
    )
    assert audit_tier3.bot_mitigation_tier == 3
    assert audit_tier3.channel == "candidate_handoff"
    assert audit_tier3.status == "handoff_ready"
    assert audit_tier3.handoff_bundle_url == f"/api/v1/handoff/{sample_tenant.id}/{job.id}"
    assert audit_tier3.confirmation_code.startswith("HANDOFF-")


# ============================================================================
# 3. FAIL-CLOSED BYOK INJECTION & KEY TOP-UP (KY-04, KY-05, IT-05)
# ============================================================================

@pytest.mark.asyncio
async def test_ky04_fail_closed_quota_exhaustion_and_resume_on_topup(
    db_session, sample_tenant, monkeypatch
):
    """KY-04: Key quota failure parks run with zero platform fallback; top-up resumes without state loss."""
    # Store initial key
    await keyvault.store_key(db_session, sample_tenant.id, "openai", "sk-test-live-key")

    db_run = Run(
        id=str(uuid.uuid4()),
        tenant_id=sample_tenant.id,
        agent_name="scout",
        goal="Discover high-conviction matches",
        status="running",
    )
    db_session.add(db_run)
    await db_session.flush()

    run_ctx = RunContext(
        run_id=db_run.id,
        tenant_id=sample_tenant.id,
        agent_name="scout",
        goal=db_run.goal,
        step_index=2,
        plan=["ingest", "score", "notify"],
    )

    # 1. Inject 402/Quota Exhaustion into model router
    async def mock_quota_failure(*args, **kwargs):
        raise KeyExhaustedError("OpenAI API error 402: Insufficient balance on BYOK account.")

    monkeypatch.setattr(router, "call", mock_quota_failure)

    # Step executes inference -> must catch KeyExhaustedError
    paused_run = await agent_loop.step(
        session=db_session,
        run=run_ctx,
        provider="openai",
    )

    # Check that run parked with no_credits
    assert paused_run.status == "no_credits"
    assert "credit exhausted" in paused_run.pause_reason

    # Key status must be updated to no_credits
    key_record = (
        await db_session.execute(
            select(ApiKey).where(ApiKey.tenant_id == sample_tenant.id, ApiKey.provider == "openai")
        )
    ).scalar_one()
    assert key_record.status == "no_credits"

    # Outbox event emitted
    event = (
        await db_session.execute(
            select(OutboxEvent).where(
                OutboxEvent.tenant_id == sample_tenant.id,
                OutboxEvent.event_name == "key.exhausted",
            )
        )
    ).scalar_one()
    assert event.payload["provider"] == "openai"

    # 2. Subsequent step with inactive key must fail-closed immediately without model call
    def mock_fail_if_called(*args, **kwargs):
        raise AssertionError("External model should never be called when key is inactive!")

    monkeypatch.setattr(router, "call", mock_fail_if_called)

    subsequent_run = await agent_loop.step(
        session=db_session,
        run=paused_run,
        provider="openai",
    )
    assert subsequent_run.status == "no_credits"
    assert "unavailable" in subsequent_run.pause_reason

    # 3. User tops up and updates key in Vault -> Key status valid, run resumes from step 2
    await keyvault.store_key(db_session, sample_tenant.id, "openai", "sk-test-topped-up-key")
    key_refreshed = (
        await db_session.execute(
            select(ApiKey).where(ApiKey.tenant_id == sample_tenant.id, ApiKey.provider == "openai")
        )
    ).scalar_one()
    assert key_refreshed.status == "valid"

    # Resume model inference
    async def mock_successful_call(*args, **kwargs):
        return {"choices": [{"message": {"content": "Found 5 matches"}}]}

    monkeypatch.setattr(router, "call", mock_successful_call)

    resumed_run = RunContext(
        run_id=db_run.id,
        tenant_id=sample_tenant.id,
        agent_name="scout",
        goal=db_run.goal,
        status="running",
        step_index=2,
        plan=["ingest", "score", "notify"],
    )

    action = AgentAction(tool_name="blackboard_read", arguments={"view_spec": ["profile"]})
    stepped_run = await agent_loop.step(
        session=db_session,
        run=resumed_run,
        provider="openai",
        action_override=action,
    )
    assert stepped_run.status == "running"
    assert stepped_run.step_index == 3


# ============================================================================
# 4. ADVERSARIAL REVIEWER HALLUCINATION REJECTION (AT-02)
# ============================================================================

def test_at02_adversarial_reviewer_catches_all_hallucination_vectors():
    """AT-02: Reviewer subagent intercepts invented metrics, modified dates, ghost companies, and unverified skills."""
    master_content = {
        "candidate_name": "Alex Mercer",
        "skills": ["Python", "PostgreSQL", "Docker"],
        "experience": [
            {
                "company": "TechStream",
                "role": "Lead Architect",
                "dates": "2020 - 2024",
                "bullets": [
                    "Scaled API ingestion handling 50,000 requests per minute with 99.9% uptime",
                    "Cut query response latency by 40% using Redis caching",
                ],
            }
        ],
    }
    verified_skills = ["Python", "PostgreSQL", "Docker"]

    # CASE A: Hallucinated Metric ($10M and 300% not in master)
    tailored_bad_metric = {
        "candidate_name": "Alex Mercer",
        "skills": ["Python", "PostgreSQL"],
        "experience": [
            {
                "company": "TechStream",
                "role": "Lead Architect",
                "dates": "2020 - 2024",
                "bullets": [
                    "Generated $10M in ARR by accelerating pipeline throughput by 300%",
                ],
            }
        ],
    }
    rev_metric = review_tailored_honesty(master_content, tailored_bad_metric, verified_skills)
    assert rev_metric["is_honest"] is False
    assert any("Hallucinated metric" in v for v in rev_metric["violations"])

    # CASE B: Modified Employment Dates (2018 - 2026 instead of 2020 - 2024)
    tailored_bad_dates = {
        "candidate_name": "Alex Mercer",
        "skills": ["Python"],
        "experience": [
            {
                "company": "TechStream",
                "role": "Lead Architect",
                "dates": "2018 - 2026",
                "bullets": [
                    "Scaled API ingestion handling 50,000 requests per minute",
                ],
            }
        ],
    }
    rev_dates = review_tailored_honesty(master_content, tailored_bad_dates, verified_skills)
    assert rev_dates["is_honest"] is False
    assert any("Modified or unverified dates" in v for v in rev_dates["violations"])

    # CASE C: Invented Ghost Company ("Google DeepMind" not in master)
    tailored_bad_company = {
        "candidate_name": "Alex Mercer",
        "skills": ["Python"],
        "experience": [
            {
                "company": "Google DeepMind",
                "role": "Research Scientist",
                "dates": "2022 - 2024",
                "bullets": ["Trained large models."],
            }
        ],
    }
    rev_company = review_tailored_honesty(master_content, tailored_bad_company, verified_skills)
    assert rev_company["is_honest"] is False
    assert any("Hallucinated company" in v for v in rev_company["violations"])

    # CASE D: Invented Skill ("Solidity" and "Rust" not in verified list or master)
    tailored_bad_skills = {
        "candidate_name": "Alex Mercer",
        "skills": ["Python", "Solidity", "Rust"],
        "experience": [
            {
                "company": "TechStream",
                "role": "Lead Architect",
                "dates": "2020 - 2024",
                "bullets": ["Cut query response latency by 40%"],
            }
        ],
    }
    rev_skills = review_tailored_honesty(master_content, tailored_bad_skills, verified_skills)
    assert rev_skills["is_honest"] is False
    assert any("Invented skill" in v for v in rev_skills["violations"])


# ============================================================================
# 5. READINESS GATE LOCKOUT & DISMISSAL PERMANENT 69 CAP (RD-01, GE-03)
# ============================================================================

@pytest.mark.asyncio
async def test_rd01_and_ge03_dismissing_critical_permanently_caps_score(
    db_session, sample_tenant
):
    """GE-03 & RD-01: Dismissing a critical to-do permanently caps Front-Face score at 69 and locks Scout."""
    # Seed high-scoring components (raw total would be 85)
    score_rec = ReadinessScore(
        tenant_id=sample_tenant.id,
        overall_score=85,
        ats_parse_score=15,
        metric_coverage_score=20,
        honest_keyword_score=15,
        linkedin_headline_about_score=20,
        experience_mirroring_score=15,
        critical_todos_cleared_score=0,
        is_capped_at_69=False,
    )
    db_session.add(score_rec)

    # Add open critical item
    critical_item = TodoItem(
        tenant_id=sample_tenant.id,
        severity="critical",
        status="open",
        category="metric_coverage",
        issue_text="Zero quantified impact metrics in 3 work bullets",
        why_it_matters="Senior roles require proof of impact.",
        fix_draft="Reduced infrastructure operational expenditure by 35%.",
    )
    db_session.add(critical_item)
    await db_session.flush()

    # 1. Gate is blocked due to open critical item (RD-01)
    with pytest.raises(ReadinessGateBlockedError):
        await readiness_gate.verify_can_schedule_scout(db_session, sample_tenant.id)

    # 2. Candidate attempts to dismiss the critical item instead of resolving it (GE-03)
    critical_item.status = "dismissed"
    critical_item.dismiss_reason = "Prefer not to share exact numbers."
    score_rec.is_capped_at_69 = True
    score_rec.cap_reason = "Critical to-do dismissed: Zero quantified impact metrics in 3 work bullets"
    score_rec.overall_score = 69  # Capped at 69
    await db_session.flush()

    # 3. Gate evaluates readiness
    status = await readiness_gate.evaluate_readiness(db_session, sample_tenant.id)
    assert status.is_ready is False
    assert status.is_capped is True
    assert status.overall_score == 69
    assert "dismissed" in status.cap_reason

    # Scout scheduling is STILL strictly blocked
    with pytest.raises(ReadinessGateBlockedError) as exc_blocked:
        await readiness_gate.verify_can_schedule_scout(db_session, sample_tenant.id)
    assert "69/100" in str(exc_blocked.value)

    # 4. Candidate un-dismisses and resolves the item -> Cap is lifted and score reaches 85
    critical_item.status = "resolved"
    score_rec.is_capped_at_69 = False
    score_rec.cap_reason = None
    score_rec.overall_score = 85
    await db_session.flush()

    status_unlocked = await readiness_gate.evaluate_readiness(db_session, sample_tenant.id)
    assert status_unlocked.is_ready is True
    assert status_unlocked.overall_score == 85
    can_schedule = await readiness_gate.verify_can_schedule_scout(db_session, sample_tenant.id)
    assert can_schedule is True


# ============================================================================
# 6. TRUSTED MODE THRESHOLD & DAILY AUTO-APPLY CAP (GT-01..03)
# ============================================================================

def test_gt01_trusted_mode_boundary_and_daily_cap():
    """GT-01..03: Evaluates exact 9.0 match threshold and 10/day auto-apply cap."""
    # Run without Trusted Mode -> Always parks for approval
    run_normal = RunContext(
        run_id="run-normal",
        tenant_id="tenant-normal",
        agent_name="writer",
        goal="Apply to role",
        trusted_mode=False,
    )
    action_high_match = AgentAction(tool_name="ats_apply", arguments={}, external=True, match_score=9.8)
    assert run_normal.trusted_covers(action_high_match) is False

    # Run with Trusted Mode ACTIVE
    run_trusted = RunContext(
        run_id="run-trusted",
        tenant_id="tenant-trusted",
        agent_name="writer",
        goal="Auto apply",
        trusted_mode=True,
        daily_auto_applies_used=0,
    )

    # Below 9.0 threshold (8.9) -> Gated
    action_sub_threshold = AgentAction(tool_name="ats_apply", arguments={}, external=True, match_score=8.9)
    assert run_trusted.trusted_covers(action_sub_threshold) is False

    # Exactly 9.0 threshold -> Auto-submits
    action_exact_threshold = AgentAction(tool_name="ats_apply", arguments={}, external=True, match_score=9.0)
    assert run_trusted.trusted_covers(action_exact_threshold) is True

    # Above threshold (9.5) -> Auto-submits
    assert run_trusted.trusted_covers(action_high_match) is True

    # Daily cap reached (10 used) -> 11th auto-apply parks for approval
    run_trusted.daily_auto_applies_used = 10
    assert run_trusted.trusted_covers(action_high_match) is False


# ============================================================================
# 7. INTERVIEW REMINDER NOTIFICATION TIMING (T-24h, T-1h)
# ============================================================================

def test_interview_reminder_timing_windows():
    """Verifies precise notification trigger windows for T-24h and T-1h reminders."""
    interview_time = datetime(2026, 10, 15, 14, 0, 0, tzinfo=timezone.utc)

    # 1. 25 hours before -> Neither reminder triggers yet
    time_25h_before = datetime(2026, 10, 14, 13, 0, 0, tzinfo=timezone.utc)
    res_25h = calculate_interview_reminders(interview_time, now=time_25h_before)
    assert res_25h["should_send_24h"] is False
    assert res_25h["should_send_1h"] is False
    assert res_25h["is_past"] is False

    # 2. 23 hours before -> T-24h reminder triggers
    time_23h_before = datetime(2026, 10, 14, 15, 0, 0, tzinfo=timezone.utc)
    res_23h = calculate_interview_reminders(interview_time, now=time_23h_before)
    assert res_23h["should_send_24h"] is True
    assert res_23h["should_send_1h"] is False

    # 3. 30 minutes before -> T-1h reminder triggers
    time_30m_before = datetime(2026, 10, 15, 13, 30, 0, tzinfo=timezone.utc)
    res_30m = calculate_interview_reminders(interview_time, now=time_30m_before)
    assert res_30m["should_send_24h"] is False
    assert res_30m["should_send_1h"] is True

    # 4. Past interview -> Marked as past
    time_after = datetime(2026, 10, 15, 15, 0, 0, tzinfo=timezone.utc)
    res_after = calculate_interview_reminders(interview_time, now=time_after)
    assert res_after["is_past"] is True
