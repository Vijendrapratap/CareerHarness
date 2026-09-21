"""Celery application and queue lane configurations meeting ST-04 specifications."""

from typing import Any, Dict

QUEUE_LANES: Dict[str, Dict[str, Any]] = {
    "fast": {
        "description": "High-priority probes, webhooks, and key validation checks",
        "concurrency": 8,
    },
    "agent_loop": {
        "description": "Interactive agent execution steps and LLM inference calls",
        "concurrency": 4,
    },
    "batch": {
        "description": "Background batch apply fan-out, heavy scrapers, and document parsing",
        "concurrency": 2,
    },
}

TASK_ROUTES: Dict[str, str] = {
    "tasks.validate_key_probe": "fast",
    "tasks.publish_outbox_events": "fast",
    "tasks.execute_agent_step": "agent_loop",
    "tasks.batch_apply_fanout": "batch",
    "tasks.scrape_job_board": "batch",
}


def get_queue_for_task(task_name: str) -> str:
    """Returns designated lane for task execution (ST-04)."""
    return TASK_ROUTES.get(task_name, "fast")
