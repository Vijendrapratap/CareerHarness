import pytest

from app.domain.journey import (
    JourneyRegressionError,
    get_or_create_journey,
    refresh_stage_from_readiness,
    set_stage,
)
from app.domain.models import ReadinessScore, TodoItem


@pytest.mark.asyncio
async def test_new_tenant_starts_in_counsel(db_session, sample_tenant):
    journey = await get_or_create_journey(db_session, sample_tenant.id)
    assert journey.stage == "counsel"


@pytest.mark.asyncio
async def test_stage_does_not_move_backward(db_session, sample_tenant):
    await set_stage(db_session, sample_tenant.id, "todos")
    with pytest.raises(JourneyRegressionError):
        await set_stage(db_session, sample_tenant.id, "counsel")


@pytest.mark.asyncio
async def test_ready_todos_advance_to_mailbox(db_session, sample_tenant):
    await set_stage(db_session, sample_tenant.id, "todos")

    # Score 80 and no open critical todos -> advances to mailbox
    score = ReadinessScore(tenant_id=sample_tenant.id, overall_score=80)
    db_session.add(score)
    await db_session.flush()

    new_stage = await refresh_stage_from_readiness(db_session, sample_tenant.id)
    assert new_stage == "mailbox"

    # Second case: with open critical todo, remains on todos
    todo = TodoItem(
        tenant_id=sample_tenant.id,
        category="bullet",
        severity="critical",
        issue_text="Missing metrics",
        why_it_matters="Impact unmeasured",
        fix_draft="Added 40% improvement",
        status="open",
    )
    db_session.add(todo)
    await db_session.flush()

    journey = await get_or_create_journey(db_session, sample_tenant.id)
    journey.stage = "todos"
    await db_session.flush()

    blocked_stage = await refresh_stage_from_readiness(db_session, sample_tenant.id)
    assert blocked_stage == "todos"
