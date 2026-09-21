"""Transactional Outbox Pattern for reliable event publishing to Redis Streams."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import OutboxEvent

# Canonical Event Catalog from Architecture Spec (§3.4)
VALID_EVENTS = {
    "user.registered",
    "key.validated",
    "roles.selected",
    "resume.parsed",
    "linkedin.captured",
    "gaps.computed",
    "todo.completed",
    "readiness.passed",
    "email.connected",
    "scout.started",
    "jobs.found",
    "batch.created",
    "batch.approved",
    "tailor.done",
    "review.done",
    "cl.done",
    "version.saved",
    "apply.submitted",
    "email.opened",
    "email.replied",
    "outcome.recorded",
    "entitlement.changed",
    "key.failed",
    "key.exhausted",
    "run.parked",
    "stories.extracted",
}


class MockStreamClient:
    """In-memory Redis Streams mock for testing and decoupled execution."""

    def __init__(self):
        self.published_messages: List[Dict[str, Any]] = []

    async def xadd(self, stream_name: str, fields: Dict[str, Any]) -> str:
        msg_id = f"{int(datetime.now(timezone.utc).timestamp() * 1000)}-0"
        self.published_messages.append({"id": msg_id, "stream": stream_name, "fields": fields})
        return msg_id


class OutboxService:
    """Manages transactional outbox storage and relay dispatch."""

    @staticmethod
    async def record_event(
        session: AsyncSession,
        tenant_id: str,
        event_name: str,
        payload: Dict[str, Any],
    ) -> OutboxEvent:
        """Writes an outbox event inside the active DB transaction.

        Guarantees that state changes and events are atomically committed (ST-03).
        """
        if event_name not in VALID_EVENTS:
            raise ValueError(f"Unknown event: '{event_name}'. Must be one of {VALID_EVENTS}")

        event = OutboxEvent(
            tenant_id=tenant_id,
            event_name=event_name,
            payload=payload,
            status="pending",
        )
        session.add(event)
        await session.flush()
        return event

    @staticmethod
    async def dispatch_pending_events(
        session: AsyncSession,
        stream_client: Any,
        tenant_id: Optional[str] = None,
        stream_name: str = "career_harness_events",
        batch_size: int = 50,
    ) -> int:
        """Relays pending outbox events to Redis Streams and marks them published."""
        query = select(OutboxEvent).where(OutboxEvent.status == "pending")
        if tenant_id:
            query = query.where(OutboxEvent.tenant_id == tenant_id)
        query = query.order_by(OutboxEvent.created_at.asc()).limit(batch_size)
        result = await session.execute(query)
        events = result.scalars().all()

        dispatched_count = 0
        for ev in events:
            try:
                # Dispatch to Redis stream
                fields = {
                    "event_id": ev.id,
                    "tenant_id": ev.tenant_id,
                    "event_name": ev.event_name,
                    "payload": json.dumps(ev.payload),
                    "created_at": ev.created_at.isoformat(),
                }
                if hasattr(stream_client, "xadd"):
                    if callable(stream_client.xadd):
                        import inspect
                        if inspect.iscoroutinefunction(stream_client.xadd):
                            await stream_client.xadd(stream_name, fields)
                        else:
                            stream_client.xadd(stream_name, fields)

                ev.status = "published"
                ev.published_at = datetime.now(timezone.utc)
                dispatched_count += 1
            except Exception:
                ev.retry_count += 1
                if ev.retry_count > 5:
                    ev.status = "failed"

        await session.flush()
        return dispatched_count


outbox = OutboxService()
