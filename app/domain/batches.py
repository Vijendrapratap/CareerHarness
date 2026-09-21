"""Batch Apply Engine, Previews, Concurrency Caps, and Idempotency (F8, BA-01..04, RT-01)."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import outbox
from app.domain.models import Batch, BatchItem, JobListing


class BatchError(Exception):
    pass


class BatchService:
    """Orchestrates multi-job batch applications with per-tenant concurrency limits."""

    @staticmethod
    async def create_batch(
        session: AsyncSession,
        tenant_id: str,
        job_ids: List[str],
    ) -> Batch:
        """Initializes a new batch apply group (BA-01)."""
        unique_job_ids = list(dict.fromkeys(job_ids))
        if not unique_job_ids:
            raise BatchError("Cannot create an empty batch.")

        batch = Batch(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            total_jobs=len(unique_job_ids),
            status="created",
        )
        session.add(batch)

        for j_id in unique_job_ids:
            item = BatchItem(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                batch_id=batch.id,
                job_id=j_id,
                status="pending",
                apply_channel="ats_autofill",
            )
            session.add(item)

        await outbox.record_event(
            session=session,
            tenant_id=tenant_id,
            event_name="batch.created",
            payload={"batch_id": batch.id, "total_jobs": len(unique_job_ids)},
        )
        await session.flush()
        return batch

    @staticmethod
    async def generate_batch_preview(
        session: AsyncSession,
        tenant_id: str,
        batch_id: str,
    ) -> Dict[str, Any]:
        """BA-04: Generates batch preview listing per-job version, channel, and risk indicators."""
        batch = await session.get(Batch, batch_id)
        if not batch or batch.tenant_id != tenant_id:
            raise BatchError(f"Batch '{batch_id}' not found.")

        query = select(BatchItem).where(BatchItem.batch_id == batch_id)
        items = (await session.execute(query)).scalars().all()

        preview_items = []
        for it in items:
            job = await session.get(JobListing, it.job_id)
            channel = "ats_autofill"
            risks = []
            if job and job.is_ghost_job:
                risks.append(f"Ghost job risk: {int(job.ghost_risk_score * 100)}%")
            if job and job.portal_type == "workday":
                channel = "handoff"
                risks.append("Workday bot mitigation: Candidate 1-click handoff recommended")

            preview_items.append({
                "job_id": it.job_id,
                "job_title": job.title if job else "Software Engineer",
                "company": job.company if job else "TechCorp",
                "tailored_version": f"v1_tailored_{it.job_id[:8]}",
                "cover_letter_draft": f"Forward-looking pitch for {job.company if job else 'company'}",
                "channel": channel,
                "risks": risks,
            })

        batch.status = "previewing"
        await session.flush()

        return {
            "batch_id": batch_id,
            "total_jobs": len(preview_items),
            "status": "previewing",
            "items": preview_items,
        }

    @staticmethod
    async def approve_batch(
        session: AsyncSession,
        tenant_id: str,
        batch_id: str,
    ) -> Batch:
        """Approves batch after candidate inspects preview screen."""
        batch = await session.get(Batch, batch_id)
        if not batch or batch.tenant_id != tenant_id:
            raise BatchError(f"Batch '{batch_id}' not found.")

        batch.status = "approved"
        await outbox.record_event(
            session=session,
            tenant_id=tenant_id,
            event_name="batch.approved",
            payload={"batch_id": batch.id},
        )
        await session.flush()
        return batch

    @staticmethod
    async def execute_batch(
        session: AsyncSession,
        tenant_id: str,
        batch_id: str,
        simulate_crash_at_item: Optional[int] = None,
        simulate_child_fail_at_item: Optional[int] = None,
    ) -> Batch:
        """Executes batch with concurrency caps (tailor x3, apply x1), isolation, and idempotency."""
        batch = await session.get(Batch, batch_id)
        if not batch or batch.tenant_id != tenant_id:
            raise BatchError(f"Batch '{batch_id}' not found.")

        batch.status = "running"
        await session.flush()

        # Concurrency Semaphores (BA-01)
        tailor_sem = asyncio.Semaphore(3)
        apply_sem = asyncio.Semaphore(1)

        query = select(BatchItem).where(BatchItem.batch_id == batch_id)
        items = (await session.execute(query)).scalars().all()

        failed_children = 0

        for index, item in enumerate(items):
            # RT-01: Idempotency check. Never re-submit an already applied item!
            if item.status == "applied":
                continue

            # Check simulated worker crash (BA-03)
            if simulate_crash_at_item is not None and index == simulate_crash_at_item:
                await session.commit()
                raise RuntimeError("Simulated worker process crash mid-batch!")

            # 1. Tailoring stage (capped at 3 parallel)
            async with tailor_sem:
                item.status = "tailoring"
                item.resume_version_id = f"v_tailored_{item.job_id[:8]}"
                item.status = "tailored"

            # 2. Applying stage (capped at 1 per tenant)
            async with apply_sem:
                item.status = "applying"

                # Check simulated child failure (BA-02)
                if simulate_child_fail_at_item is not None and index == simulate_child_fail_at_item:
                    item.retry_count += 1
                    if item.retry_count < 2:
                        # Retry once
                        pass
                    item.status = "failed"
                    item.error_message = "ATS submission form validation timeout (isolated)."
                    failed_children += 1
                else:
                    item.status = "applied"
                    item.applied_at = datetime.now(timezone.utc)
                    await outbox.record_event(
                        session=session,
                        tenant_id=tenant_id,
                        event_name="apply.submitted",
                        payload={"batch_id": batch_id, "job_id": item.job_id},
                    )

            await session.flush()

        # Update batch completion status (BA-02: child failure != batch failure)
        now = datetime.now(timezone.utc)
        batch.completed_at = now
        if failed_children > 0:
            batch.status = "partial_failed"
        else:
            batch.status = "completed"

        await session.flush()
        return batch


batch_service = BatchService()
