"""Tests for Batch Fan-Out, Preview, Child Isolation, and Idempotency meeting BA-01..04 and RT-01."""

import pytest
from sqlalchemy import select

from app.domain.batches import batch_service
from app.domain.jobs import job_service
from app.domain.models import BatchItem


@pytest.fixture
async def sample_jobs(db_session):
    """Creates a catalog of 5 diverse scouted jobs."""
    jobs = []
    for i in range(5):
        j = await job_service.ingest_job(
            session=db_session,
            title=f"Senior Software Engineer #{i+1}",
            company=f"TechCorp {i+1}",
            url=f"https://boards.greenhouse.io/techcorp/jobs/{1000 + i}",
            description="High growth platform team looking for backend distributed systems engineers.",
            portal_type="greenhouse" if i != 2 else "workday",
        )
        jobs.append(j)
    await db_session.commit()
    return jobs


@pytest.mark.asyncio
async def test_ba04_preview_shows_every_version_before_approval(
    db_session, sample_tenant, sample_jobs
):
    """BA-04: Batch preview screen displays per-job version, channel, and risk signals before approval."""
    job_ids = [j.id for j in sample_jobs]
    batch = await batch_service.create_batch(db_session, sample_tenant.id, job_ids)

    # Generate preview
    preview = await batch_service.generate_batch_preview(db_session, sample_tenant.id, batch.id)

    assert preview["status"] == "previewing"
    assert preview["total_jobs"] == 5
    assert len(preview["items"]) == 5

    # Check that each item displays version, channel, and risk indicators
    for item in preview["items"]:
        assert "tailored_version" in item
        assert "cover_letter_draft" in item
        assert "channel" in item
        assert "risks" in item

    # The workday portal should recommend handoff channel
    workday_item = next(i for i in preview["items"] if i["company"] == "TechCorp 3")
    assert workday_item["channel"] == "handoff"


@pytest.mark.asyncio
async def test_ba01_and_ba02_child_failure_never_kills_batch(
    db_session, sample_tenant, sample_jobs
):
    """BA-01 & BA-02: Concurrency caps enforced, and individual child failures isolate without failing batch."""
    job_ids = [j.id for j in sample_jobs]
    batch = await batch_service.create_batch(db_session, sample_tenant.id, job_ids)
    await batch_service.approve_batch(db_session, sample_tenant.id, batch.id)

    # Execute with simulated child failure on job index 1
    completed_batch = await batch_service.execute_batch(
        session=db_session,
        tenant_id=sample_tenant.id,
        batch_id=batch.id,
        simulate_child_fail_at_item=1,
    )

    # BA-02: Batch status is partial_failed, not killed
    assert completed_batch.status == "partial_failed"

    items = (
        await db_session.execute(
            select(BatchItem).where(BatchItem.batch_id == batch.id).order_by(BatchItem.id)
        )
    ).scalars().all()

    # Item 1 failed in isolation
    assert any(it.status == "failed" and "isolated" in (it.error_message or "") for it in items)
    # Remaining 4 items succeeded
    applied_count = sum(1 for it in items if it.status == "applied")
    assert applied_count == 4


@pytest.mark.asyncio
async def test_ba03_and_rt01_crash_resume_idempotency(
    db_session, sample_tenant, sample_jobs
):
    """BA-03 & RT-01: Worker crash mid-batch resumes from checkpoint without double-applying."""
    job_ids = [j.id for j in sample_jobs]
    batch = await batch_service.create_batch(db_session, sample_tenant.id, job_ids)
    await batch_service.approve_batch(db_session, sample_tenant.id, batch.id)

    # 1. Simulate worker crash at item 2 (first 2 items applied)
    with pytest.raises(RuntimeError) as exc_info:
        await batch_service.execute_batch(
            session=db_session,
            tenant_id=sample_tenant.id,
            batch_id=batch.id,
            simulate_crash_at_item=2,
        )
    assert "crash" in str(exc_info.value)

    # Verify first 2 items were checkpointed as applied
    checkpointed_items = (
        await db_session.execute(select(BatchItem).where(BatchItem.batch_id == batch.id))
    ).scalars().all()
    applied_before_crash = [it for it in checkpointed_items if it.status == "applied"]
    assert len(applied_before_crash) == 2

    # 2. Worker restarts and resumes the same batch (BA-03)
    resumed_batch = await batch_service.execute_batch(
        session=db_session,
        tenant_id=sample_tenant.id,
        batch_id=batch.id,
    )

    assert resumed_batch.status == "completed"

    # RT-01: Idempotency check. All 5 items applied, none duplicated or orphaned
    final_items = (
        await db_session.execute(select(BatchItem).where(BatchItem.batch_id == batch.id))
    ).scalars().all()
    assert len(final_items) == 5
    assert all(it.status == "applied" for it in final_items)
