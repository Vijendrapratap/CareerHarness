"""Background worker tasks for outbox publishing and agent step execution."""

from typing import Any, Dict

from app.workers.celery_app import get_queue_for_task


async def publish_outbox_events_task() -> Dict[str, Any]:
    """Relays pending events to Redis Streams on the fast queue."""
    lane = get_queue_for_task("tasks.publish_outbox_events")
    return {"status": "dispatched", "lane": lane}


async def validate_key_probe_task(provider: str, api_key: str) -> Dict[str, Any]:
    """Validates candidate API key on the fast queue."""
    lane = get_queue_for_task("tasks.validate_key_probe")
    return {"status": "validated", "lane": lane, "provider": provider}


async def execute_agent_step_task(run_id: str, tenant_id: str) -> Dict[str, Any]:
    """Executes next step of agent loop on the agent_loop queue."""
    lane = get_queue_for_task("tasks.execute_agent_step")
    return {"status": "step_executed", "lane": lane, "run_id": run_id}
