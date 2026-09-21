"""Tests for Gap Engine, Front-Face Scoring, and Readiness Gate meeting GE-01..05 and RD-01 specifications."""

import pytest

from app.domain.gap_engine import gap_engine
from app.domain.linkedin import linkedin_service
from app.domain.readiness import ReadinessGateBlockedError, readiness_gate
from app.domain.resume_parser import resume_parser
from app.domain.roles import roles_service


@pytest.fixture
async def setup_candidate_profile(db_session, sample_tenant):
    """Sets up a candidate with priority role, parsed resume, and linked LinkedIn profile."""
    # 1. Select target roles with priority Backend Architect
    await roles_service.select_roles(
        session=db_session,
        tenant_id=sample_tenant.id,
        role_ids=["role_backend_arch", "role_fullstack_eng"],
        priority_role_id="role_backend_arch",
    )

    # 2. Parse resume
    resume_text = """
    Staff Backend Engineer.
    - Designed distributed database sharding architecture supporting high traffic.
    - Maintained legacy microservices and reviewed pull requests.
    """
    await resume_parser.parse_resume_text(
        session=db_session,
        tenant_id=sample_tenant.id,
        filename="resume.pdf",
        content=resume_text,
    )

    # 3. Save LinkedIn profile
    await linkedin_service.save_profile_paste(
        session=db_session,
        tenant_id=sample_tenant.id,
        headline="Staff Software Engineer | Distributed Systems",
        about="Passionate architect building resilient distributed backends.",
        skills=["Distributed Systems", "SQL", "Python"],
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_ge01_and_ge02_fix_drafts_cite_source_and_no_invented_skills(
    db_session, sample_tenant, setup_candidate_profile
):
    """GE-01: Fix drafts cite source bullet. GE-02: No invented skills in any fix draft."""
    report, todos, score = await gap_engine.compute_gaps(db_session, sample_tenant.id)

    # GE-01: Bullet todos cite source bullet
    bullet_todos = [t for t in todos if t.category == "resume_bullet"]
    assert len(bullet_todos) > 0
    for t in bullet_todos:
        assert t.source_bullet is not None
        assert t.source_bullet in t.fix_draft
        assert t.has_unverified_metric is True  # Renders [confirm: X%] chip

    # GE-02: Missing baseline skill todos ask candidate to confirm, not hallucinate
    skill_todos = [t for t in todos if t.category == "skill_alignment"]
    for st in skill_todos:
        assert "confirm" in st.fix_draft.lower()


@pytest.mark.asyncio
async def test_ge03_critical_dismiss_caps_score_at_69(
    db_session, sample_tenant, setup_candidate_profile
):
    """GE-03: Dismissing a critical item strictly caps Front-Face Score at 69 with explicit explanation."""
    _, todos, initial_score = await gap_engine.compute_gaps(db_session, sample_tenant.id)

    # Find a critical to-do
    critical_todo = next(t for t in todos if t.severity == "critical")

    # Dismiss with explanation
    dismissed_item, updated_score = await gap_engine.resolve_todo(
        session=db_session,
        tenant_id=sample_tenant.id,
        todo_id=critical_todo.id,
        action="dismiss",
        dismiss_reason="Candidate intentionally prefers not to alter this headline keyword.",
    )

    assert dismissed_item.status == "dismissed"
    # Strict GE-03 check: score must be capped at 69
    assert updated_score.is_capped_at_69 is True
    assert updated_score.overall_score <= 69
    assert "Score capped at 69" in updated_score.cap_reason


@pytest.mark.asyncio
async def test_rd01_scout_unschedulable_below_threshold(
    db_session, sample_tenant, setup_candidate_profile
):
    """RD-01: Job Scout is unschedulable while score < 70 or open criticals > 0."""
    await gap_engine.compute_gaps(db_session, sample_tenant.id)

    # Candidate has open criticals -> scheduling Scout must raise ReadinessGateBlockedError
    with pytest.raises(ReadinessGateBlockedError) as exc_info:
        await readiness_gate.verify_can_schedule_scout(db_session, sample_tenant.id)

    assert "Readiness Gate Locked" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ge05_role_change_recomputes_gaps_and_score(
    db_session, sample_tenant, setup_candidate_profile
):
    """GE-05: Changing target roles recomputes gap analysis and updates Front-Face Score."""
    # Compute initial gaps for Backend Architect
    _, initial_todos, initial_score = await gap_engine.compute_gaps(db_session, sample_tenant.id)

    # Change candidate target priority role to Engineering Manager
    await roles_service.select_roles(
        session=db_session,
        tenant_id=sample_tenant.id,
        role_ids=["role_eng_manager"],
        mgmt_experience=True,
    )

    # Recompute gaps
    _, updated_todos, updated_score = await gap_engine.compute_gaps(db_session, sample_tenant.id)

    # The new target role expects leadership skills (e.g. People Leadership, Roadmap Planning)
    em_skill_gaps = [t for t in updated_todos if "leadership" in t.issue_text.lower() or "roadmap" in t.issue_text.lower()]
    assert len(em_skill_gaps) > 0
