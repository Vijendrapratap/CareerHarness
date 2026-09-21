"""Tests for the Thin In-House Harness Core (Registry, Gate, Loop, Checkpointer)."""

import uuid

import pytest
from sqlalchemy import select

from app.core.keyvault import keyvault
from app.domain.models import Approval, Checkpoint, OutboxEvent, Run
from app.harness.checkpointer import checkpointer
from app.harness.loop import agent_loop
from app.harness.registry import ToolPermissionError, registry
from app.harness.run import AgentAction, RunContext


@pytest.mark.asyncio
async def test_harness_tool_registry_and_fail_closed_tenancy():
    """Verifies tool registry permissions and fail-closed tenant scoping."""
    tool = registry.get("blackboard_read")
    assert tool.meta.name == "blackboard_read"
    assert tool.meta.external is False

    # Calling tool without tenant_id must raise ToolPermissionError
    with pytest.raises(ToolPermissionError):
        await tool.execute(tenant_id="")

    # Calling tool with valid tenant_id succeeds
    output = await tool.execute(tenant_id="test-tenant-123", view_spec=["profile"])
    assert isinstance(output, dict)


@pytest.mark.asyncio
async def test_harness_internal_step_and_checkpoint(db_session, sample_tenant):
    """Verifies that an internal step executes and saves a checkpoint."""
    await keyvault.store_key(db_session, sample_tenant.id, "openai", "sk-test-internal-step-key")

    db_run = Run(
        id=str(uuid.uuid4()),
        tenant_id=sample_tenant.id,
        agent_name="scout",
        goal="Identify matches",
        status="running",
    )
    db_session.add(db_run)
    await db_session.flush()

    run_ctx = RunContext(
        run_id=db_run.id,
        tenant_id=sample_tenant.id,
        agent_name="scout",
        goal=db_run.goal,
    )

    action = AgentAction(
        tool_name="blackboard_read",
        arguments={"view_spec": ["roles"]},
        external=False,
    )

    # Execute step
    result_run = await agent_loop.step(
        session=db_session,
        run=run_ctx,
        provider="openai",
        action_override=action,
    )

    # Asserts step completed and checkpoint exists
    assert result_run.step_index == 1
    assert len(result_run.history) == 1
    assert result_run.status == "running"

    checkpoints = (
        await db_session.execute(
            select(Checkpoint).where(Checkpoint.run_id == db_run.id)
        )
    ).scalars().all()
    assert len(checkpoints) == 1
    assert checkpoints[0].step_index == 1


@pytest.mark.asyncio
async def test_harness_external_gate_parks_run_and_emits_event(db_session, sample_tenant):
    """Verifies that external actions convert to pending approvals and park the run."""
    await keyvault.store_key(db_session, sample_tenant.id, "openai", "sk-test-external-gate-key")

    db_run = Run(
        id=str(uuid.uuid4()),
        tenant_id=sample_tenant.id,
        agent_name="writer",
        goal="Apply to role",
        status="running",
    )
    db_session.add(db_run)
    await db_session.flush()

    run_ctx = RunContext(
        run_id=db_run.id,
        tenant_id=sample_tenant.id,
        agent_name="writer",
        goal=db_run.goal,
        trusted_mode=False,  # Human-in-the-loop required
    )

    # External tool action without Trusted Mode
    action = AgentAction(
        tool_name="ats_apply",
        arguments={"job_id": "job_greenhouse_99", "payload": {"resume_id": "v1"}},
        external=True,
    )

    # Execute step -> should park
    result_run = await agent_loop.step(
        session=db_session,
        run=run_ctx,
        provider="openai",
        action_override=action,
    )

    assert result_run.status == "awaiting_approval"
    assert "awaiting_approval" in result_run.pause_reason

    # Verify pending Approval record was created
    approval = (
        await db_session.execute(
            select(Approval).where(Approval.run_id == db_run.id)
        )
    ).scalar_one()
    assert approval.status == "pending"
    assert approval.tool_name == "ats_apply"
    assert approval.payload["job_id"] == "job_greenhouse_99"

    # Verify run.parked event was written to outbox
    event = (
        await db_session.execute(
            select(OutboxEvent).where(
                OutboxEvent.tenant_id == sample_tenant.id,
                OutboxEvent.event_name == "run.parked",
            )
        )
    ).scalar_one()
    assert event.payload["approval_id"] == approval.id


@pytest.mark.asyncio
async def test_harness_trusted_mode_auto_apply_bypass(db_session, sample_tenant):
    """Verifies that Trusted Mode executes external apply automatically if match >= 9/10 (D5)."""
    await keyvault.store_key(db_session, sample_tenant.id, "openai", "sk-test-trusted-mode-key")

    db_run = Run(
        id=str(uuid.uuid4()),
        tenant_id=sample_tenant.id,
        agent_name="writer",
        goal="Auto apply in trusted mode",
        status="running",
    )
    db_session.add(db_run)
    await db_session.flush()

    run_ctx = RunContext(
        run_id=db_run.id,
        tenant_id=sample_tenant.id,
        agent_name="writer",
        goal=db_run.goal,
        trusted_mode=True,  # Trusted Mode active
        daily_auto_applies_used=2,
    )

    action = AgentAction(
        tool_name="ats_apply",
        arguments={"job_id": "job_perfect_match", "payload": {}},
        external=True,
        match_score=9.6,  # Qualifies for auto-apply (>= 9.0)
    )

    # Step should NOT park
    result_run = await agent_loop.step(
        session=db_session,
        run=run_ctx,
        provider="openai",
        action_override=action,
    )

    assert result_run.status == "running"
    assert result_run.daily_auto_applies_used == 3
    assert result_run.step_index == 1


@pytest.mark.asyncio
async def test_harness_checkpointer_crash_resume(db_session, sample_tenant):
    """Verifies that Checkpointer accurately restores a Run context after a simulated crash."""
    run_id = str(uuid.uuid4())
    db_run = Run(
        id=run_id,
        tenant_id=sample_tenant.id,
        agent_name="orchestrator",
        goal="Complete 5-stage application pipeline",
        status="running",
    )
    db_session.add(db_run)
    await db_session.flush()

    run_ctx = RunContext(
        run_id=run_id,
        tenant_id=sample_tenant.id,
        agent_name="orchestrator",
        goal=db_run.goal,
        step_index=3,
        plan=["parse", "tailor", "ats_check", "submit"],
        trusted_mode=True,
    )
    run_ctx.record_step(
        tool_name="blackboard_write",
        args={"section": "verified_skills", "data": ["Python", "FastAPI"]},
        output={"status": "written"},
    )

    # Save checkpoint
    await checkpointer.save_checkpoint(db_session, run_ctx)
    await db_session.commit()

    # Restore run as if in a new worker process
    restored = await checkpointer.restore_run(
        session=db_session,
        run_id=run_id,
        tenant_id=sample_tenant.id,
    )

    assert restored is not None
    assert restored.run_id == run_id
    assert restored.step_index == 4
    assert restored.plan == ["parse", "tailor", "ats_check", "submit"]
    assert restored.trusted_mode is True
    assert len(restored.history) == 1
    assert restored.history[0].tool_name == "blackboard_write"
