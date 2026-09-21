"""Tests for DeepSeek Harness (dsh) adapted architectural patterns.

Tests:
1. Capability Seams: Swappable ATS providers and 3-tier fallback ladder.
2. Session Event Projections: Folding event streams into live run state and UI snapshots.
3. Agent Teams & Task Board: Inter-agent handoffs, mailbox, and task lifecycle.
4. Guarded Tool Pipeline: Interceptor execution, fail-closed tenant validation, event logging.
"""

import pytest

from app.harness.pipeline import GuardedToolPipeline, PipelineAbortError
from app.harness.projections import SessionEvent, SessionProjectionRegistry
from app.harness.seams import AtsSeam
from app.harness.teams import CareerAgentTeam


@pytest.mark.asyncio
async def test_dsh_capability_seam_and_fallback_ladder():
    """Verifies DeepSeek-style Capability Seams for swappable ATS providers and 3-tier fallback."""
    seam = AtsSeam()
    assert "greenhouse" in seam.list_providers()
    assert "lever" in seam.list_providers()
    assert "email_apply" in seam.list_providers()
    assert "candidate_handoff" in seam.list_providers()

    tenant_id = "tenant-dsh-001"
    job_id = "job-gh-001"
    job_url = "https://boards.greenhouse.io/acme/jobs/123"
    resume_id = "doc-v1"
    payload = {"company_email": "jobs@acme.com", "has_connected_email": True}

    # 1. Normal run -> Tier 1 (Greenhouse stealth submit)
    res_t1 = await seam.execute_with_fallback_ladder(
        tenant_id=tenant_id,
        job_id=job_id,
        job_url=job_url,
        resume_version_id=resume_id,
        payload=payload,
        simulate_bot_block=False,
    )
    assert res_t1.success is True
    assert res_t1.tier == 1
    assert res_t1.channel == "ats_autofill"
    assert res_t1.data["portal"] == "greenhouse"

    # 2. Bot block with connected email -> Tier 2 (Email Apply Fallback)
    res_t2 = await seam.execute_with_fallback_ladder(
        tenant_id=tenant_id,
        job_id=job_id,
        job_url=job_url,
        resume_version_id=resume_id,
        payload=payload,
        simulate_bot_block=True,
    )
    assert res_t2.success is True
    assert res_t2.tier == 2
    assert res_t2.channel == "email_apply"

    # 3. Bot block without connected email -> Tier 3 (1-Click Candidate Handoff Bundle)
    res_t3 = await seam.execute_with_fallback_ladder(
        tenant_id=tenant_id,
        job_id=job_id,
        job_url=job_url,
        resume_version_id=resume_id,
        payload={"company_email": None, "has_connected_email": False},
        simulate_bot_block=True,
    )
    assert res_t3.success is True
    assert res_t3.tier == 3
    assert res_t3.channel == "candidate_handoff"
    assert "bundle_url" in res_t3.data


def test_dsh_session_event_projection_engine():
    """Verifies pure event projection folding durable event streams into live run state."""
    registry = SessionProjectionRegistry()
    run_id = "run-dsh-proj-100"
    tenant_id = "tenant-dsh-proj"

    # Initially empty
    initial_state = registry.state_of(run_id)
    assert initial_state.current_phase == "INIT"
    assert initial_state.step_count == 0

    # Fold stream of lifecycle events
    registry.append_event(
        SessionEvent(
            event_id="e1",
            tenant_id=tenant_id,
            run_id=run_id,
            event_type="turn_start",
            payload={"goal": "Apply to Stripe"},
        )
    )
    registry.append_event(
        SessionEvent(
            event_id="e2",
            tenant_id=tenant_id,
            run_id=run_id,
            event_type="tailoring_completed",
            payload={"keywords": ["Python", "FastAPI", "Distributed Systems"]},
        )
    )
    registry.append_event(
        SessionEvent(
            event_id="e3",
            tenant_id=tenant_id,
            run_id=run_id,
            event_type="honesty_review_passed",
            payload={"violations": 0},
        )
    )
    registry.append_event(
        SessionEvent(
            event_id="e4",
            tenant_id=tenant_id,
            run_id=run_id,
            event_type="ats_check_completed",
            payload={"ats_score": 92},
        )
    )
    registry.append_event(
        SessionEvent(
            event_id="e5",
            tenant_id=tenant_id,
            run_id=run_id,
            event_type="submission_settled",
            payload={"tier": 1, "code": "ATS-12345"},
        )
    )

    live_state = registry.state_of(run_id)
    assert live_state.current_phase == "COMPLETED"
    assert live_state.status == "completed"
    assert live_state.step_count == 5
    assert live_state.tailored_keywords == ["Python", "FastAPI", "Distributed Systems"]
    assert live_state.honesty_passed is True
    assert live_state.ats_score == 92
    assert live_state.active_bot_tier == 1
    assert len(live_state.timeline) == 5

    # Test client UI snapshot
    snapshot = registry.snapshot(run_id)
    assert snapshot["phase"] == "COMPLETED"
    assert snapshot["honesty_audit"] == "passed"
    assert snapshot["ats_compatibility_score"] == 92
    assert snapshot["timeline_events_count"] == 5


def test_dsh_agent_teams_taskboard_and_mailbox():
    """Verifies Agent Teams coordination (Scout -> Analyst -> Tailor -> Reviewer -> Dispatcher)."""
    team = CareerAgentTeam()
    tenant_id = "tenant-dsh-team-1"

    # 1. Scout handoffs discovered job to Analyst
    task_analyst = team.handoff(
        tenant_id=tenant_id,
        from_role="scout",
        to_role="analyst",
        task_title="Score Job: Staff Infrastructure Engineer at Uber",
        payload={"job_id": "job-uber-01", "company": "Uber"},
    )
    assert task_analyst.status == "pending"
    assert task_analyst.assigned_role == "analyst"

    # Analyst inbox should have notification message
    analyst_inbox = team.mailbox.get_inbox(tenant_id, "analyst")
    assert len(analyst_inbox) == 1
    assert "Uber" in analyst_inbox[0].subject

    # Analyst claims and completes scoring
    team.board.claim_task(task_analyst.task_id, agent_name="AnalystAgent-1")
    team.board.complete_task(task_analyst.task_id, result={"match_score": 9.4})

    # 2. Analyst handoffs scored job to Tailor
    task_tailor = team.handoff(
        tenant_id=tenant_id,
        from_role="analyst",
        to_role="tailor",
        task_title="Tailor Resume for Uber Staff Role",
        payload={"job_id": "job-uber-01", "match_score": 9.4},
    )
    assert task_tailor.assigned_role == "tailor"

    # Tailor claims and completes draft
    team.board.claim_task(task_tailor.task_id, agent_name="TailorAgent-1")
    team.board.complete_task(task_tailor.task_id, result={"draft_version_id": "doc-v2"})

    # 3. Tailor handoffs draft to Reviewer for honesty audit
    task_reviewer = team.handoff(
        tenant_id=tenant_id,
        from_role="tailor",
        to_role="reviewer",
        task_title="Audit Draft Honesty doc-v2",
        payload={"draft_version_id": "doc-v2"},
    )
    team.board.claim_task(task_reviewer.task_id, agent_name="ReviewerSubAgent-1")
    team.board.complete_task(task_reviewer.task_id, result={"honesty_verified": True})

    # Verify board state
    completed_tasks = team.board.list_tasks(tenant_id, status="completed")
    assert len(completed_tasks) == 3


@pytest.mark.asyncio
async def test_dsh_guarded_tool_execution_pipeline():
    """Verifies guarded tool execution pipeline with fail-closed tenant validation and hooks."""
    pipeline = GuardedToolPipeline()

    async def dummy_handler(tenant_id: str, value: int):
        return {"result": value * 2}

    # 1. Missing or invalid tenant_id -> PipelineAbortError (fail-closed)
    with pytest.raises(PipelineAbortError):
        await pipeline.execute_guarded(
            handler=dummy_handler,
            tenant_id="",  # Invalid tenant_id
            tool_name="test_tool",
            arguments={"value": 5},
        )

    # 2. Valid tenant -> Executes and passes through interceptors
    valid_tenant = "tenant-valid-12345"
    output = await pipeline.execute_guarded(
        handler=dummy_handler,
        tenant_id=valid_tenant,
        tool_name="test_tool",
        arguments={"value": 21},
        run_id="run-pipeline-01",
    )
    assert output["result"] == 42
