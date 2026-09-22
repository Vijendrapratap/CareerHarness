import pytest

from app.domain.journey import (
    JourneyRegressionError,
    get_or_create_journey,
    refresh_stage_from_readiness,
    set_stage,
)
from app.domain.models import TodoItem


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
async def test_optional_todos_and_mailbox_stages_move_on_to_hunt(db_session, sample_tenant):
    """To-dos and mailbox are optional: refresh moves a parked candidate on, even with open criticals."""
    await set_stage(db_session, sample_tenant.id, "todos")
    db_session.add(TodoItem(
        tenant_id=sample_tenant.id,
        category="bullet",
        severity="critical",
        issue_text="Missing metrics",
        why_it_matters="Impact unmeasured",
        fix_draft="Added 40% improvement",
        status="open",
    ))
    await db_session.flush()
    assert await refresh_stage_from_readiness(db_session, sample_tenant.id) == "hunt"


@pytest.mark.asyncio
async def test_hunt_becomes_active_after_submit(db_session, sample_tenant):
    from app.domain.journey import note_application_submitted

    # When on todos, note_application_submitted leaves todos unchanged
    await set_stage(db_session, sample_tenant.id, "todos")
    stage = await note_application_submitted(db_session, sample_tenant.id)
    assert stage == "todos"

    # When on hunt, note_application_submitted advances to active
    await set_stage(db_session, sample_tenant.id, "hunt")
    new_stage = await note_application_submitted(db_session, sample_tenant.id)
    assert new_stage == "active"
    journey = await get_or_create_journey(db_session, sample_tenant.id)
    assert journey.stage == "active"

