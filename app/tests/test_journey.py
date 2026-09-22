import pytest

from app.domain.journey import JourneyRegressionError, get_or_create_journey, set_stage


@pytest.mark.asyncio
async def test_new_tenant_starts_in_counsel(db_session, sample_tenant):
    journey = await get_or_create_journey(db_session, sample_tenant.id)
    assert journey.stage == "counsel"


@pytest.mark.asyncio
async def test_stage_does_not_move_backward(db_session, sample_tenant):
    await set_stage(db_session, sample_tenant.id, "todos")
    with pytest.raises(JourneyRegressionError):
        await set_stage(db_session, sample_tenant.id, "counsel")
