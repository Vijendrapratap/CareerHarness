"""Tests for Consulting Profiler Agent and Readiness Gate (Phase 2)."""

import pytest

from app.agents.profiler import profiler_agent
from app.domain.models import ReadinessScore, ResumeParse, RoleSelection, Story, TodoItem
from app.domain.readiness import readiness_gate


@pytest.mark.asyncio
async def test_profiler_star_story_extraction_and_reflection(db_session, sample_tenant):
    """Verifies STAR extraction and reflection against master resume bullets."""
    # Seed master resume
    master_resume = ResumeParse(
        tenant_id=sample_tenant.id,
        filename="master_resume.pdf",
        raw_text="Staff Software Engineer with expertise in Python, FastAPI, and PostgreSQL.",
        sections={
            "bullets": [
                "Architected distributed task processing pipeline using Python and Redis.",
                "Optimized database query latency by 45% through composite index redesign.",
                "Handled 10x traffic spikes and scaled pipelines to 10M events per day.",
            ]
        },
        extracted_skills=[{"name": "Python", "verified": True}],
    )
    db_session.add(master_resume)
    await db_session.flush()

    raw_notes = """
    Project: High-Throughput Ingestion
    Situation: Legacy ingestion system suffered frequent OOM crashes during traffic surges.
    Task: Rebuild the data pipeline to handle 10x traffic spikes with zero downtime.
    Action: Migrated data worker pool to Python asyncio with Redis queues and PostgreSQL batching.
    Result: Successfully supported 10M events per day with latency reduced by 45%.
    """

    stories = await profiler_agent.extract_and_persist_stories(
        session=db_session,
        tenant_id=sample_tenant.id,
        raw_notes=raw_notes,
    )

    assert len(stories) == 1
    story = stories[0]
    assert "High-Throughput Ingestion" in story.title
    assert "Legacy ingestion system" in story.situation
    assert "Python" in story.skills_demonstrated
    assert story.verified_against_master is True


@pytest.mark.asyncio
async def test_profiler_story_reflection_flags_unsupported_metrics(db_session, sample_tenant):
    """Verifies reflection flags claims that contradict or are absent in master resume."""
    # Seed master resume with NO mention of 99.99% or $1M
    master_resume = ResumeParse(
        tenant_id=sample_tenant.id,
        filename="master.pdf",
        raw_text="Backend Engineer.",
        sections={"bullets": ["Maintained internal services in Python."]},
        extracted_skills=[],
    )
    db_session.add(master_resume)
    await db_session.flush()

    raw_notes = """
    Story 1: Enterprise Migration
    Situation: Monolithic system migration.
    Task: Lead $1M migration initiative.
    Action: Led infrastructure overhaul with zero downtime.
    Result: Achieved 99.99% availability and saved $1M.
    """

    stories = await profiler_agent.extract_and_persist_stories(
        session=db_session,
        tenant_id=sample_tenant.id,
        raw_notes=raw_notes,
    )

    assert len(stories) == 1
    # Master resume did not contain "$1M" -> reflection sets verified_against_master=False
    assert stories[0].verified_against_master is False


@pytest.mark.asyncio
async def test_readiness_gate_locks_scout_below_threshold(db_session, sample_tenant):
    """RD-01: Scout is unschedulable if score < 70 or open criticals > 0."""
    # Seed score of 65 (below 70)
    score_rec = ReadinessScore(
        tenant_id=sample_tenant.id,
        overall_score=65,
        ats_parse_score=10,
        metric_coverage_score=15,
        honest_keyword_score=10,
        linkedin_headline_about_score=15,
        experience_mirroring_score=10,
        critical_todos_cleared_score=5,
    )
    db_session.add(score_rec)
    await db_session.flush()

    # Below threshold -> not ready (advisory; scouting is never blocked)
    assert not (await readiness_gate.evaluate_readiness(db_session, sample_tenant.id)).is_ready

    # Now update score to 75, but add an open critical Todo
    score_rec.overall_score = 75
    critical_todo = TodoItem(
        tenant_id=sample_tenant.id,
        severity="critical",
        status="open",
        category="metric_coverage",
        issue_text="Zero measurable metrics in 3 work bullets",
        why_it_matters="Metrics prove business impact and are required for senior roles.",
        fix_draft="Add concrete metrics (e.g. reduced latency by 30%).",
    )
    db_session.add(critical_todo)
    await db_session.flush()

    # Still not ready due to open critical
    assert not (await readiness_gate.evaluate_readiness(db_session, sample_tenant.id)).is_ready

    # Mark critical resolved -> Gate passes!
    critical_todo.status = "resolved"
    await db_session.flush()

    assert (await readiness_gate.evaluate_readiness(db_session, sample_tenant.id)).is_ready
