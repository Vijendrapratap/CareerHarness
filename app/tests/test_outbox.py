"""Tests for Transactional Outbox and Event Dispatching meeting ST-03 specifications."""

import pytest
from sqlalchemy import select

from app.core.outbox import MockStreamClient, outbox
from app.domain.models import OutboxEvent


@pytest.mark.asyncio
async def test_st03_outbox_transactional_atomicity(db_session, sample_tenant):
    """ST-03: Events recorded in a rolled-back transaction do not persist."""
    # Record event in a nested transaction that rolls back
    try:
        async with db_session.begin_nested():
            await outbox.record_event(
                session=db_session,
                tenant_id=sample_tenant.id,
                event_name="key.validated",
                payload={"provider": "openai", "masked": "sk-...1234"},
            )
            # Deliberately raise to trigger rollback
            raise RuntimeError("Simulated transaction failure")
    except RuntimeError:
        pass

    # Verify event was NOT persisted
    res = await db_session.execute(
        select(OutboxEvent).where(OutboxEvent.tenant_id == sample_tenant.id)
    )
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_st03_reliable_stream_dispatch(db_session, sample_tenant):
    """ST-03: Pending outbox events are reliably published to Redis Streams."""
    mock_redis = MockStreamClient()

    # Record two sequential lifecycle events
    ev1 = await outbox.record_event(
        session=db_session,
        tenant_id=sample_tenant.id,
        event_name="roles.selected",
        payload={"roles": ["Full Stack Engineer", "Backend Architect"], "priority": 0},
    )
    ev2 = await outbox.record_event(
        session=db_session,
        tenant_id=sample_tenant.id,
        event_name="readiness.passed",
        payload={"score": 85, "criticals_open": 0},
    )
    await db_session.commit()

    # Dispatch to Redis Streams for this tenant
    dispatched = await outbox.dispatch_pending_events(
        session=db_session,
        stream_client=mock_redis,
        tenant_id=sample_tenant.id,
        stream_name="career_harness_events",
    )
    assert dispatched == 2

    # Verify mock Redis stream received both messages
    assert len(mock_redis.published_messages) == 2
    assert mock_redis.published_messages[0]["fields"]["event_name"] == "roles.selected"
    assert mock_redis.published_messages[1]["fields"]["event_name"] == "readiness.passed"

    # Verify database status updated to published
    await db_session.refresh(ev1)
    await db_session.refresh(ev2)
    assert ev1.status == "published"
    assert ev1.published_at is not None
    assert ev2.status == "published"
    assert ev2.published_at is not None
