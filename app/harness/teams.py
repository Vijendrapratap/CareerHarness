"""Agent Teams & Task Board Coordination Seam.

Pattern borrowed from DeepSeek Harness (dsh):
Durable team roster, shared task board, and inter-agent mailbox coordination
(ctx.agentTeams) enabling continuable subagents (Scout -> Analyst -> Tailor -> Reviewer -> Dispatcher).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class TeamTask:
    task_id: str
    tenant_id: str
    assigned_role: str  # scout, analyst, tailor, reviewer, dispatcher
    title: str
    status: str  # pending, claimed, in_review, completed, failed
    payload: Dict[str, Any]
    assigned_agent: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


@dataclass
class TeamMessage:
    message_id: str
    tenant_id: str
    sender_role: str
    recipient_role: str
    subject: str
    payload: Dict[str, Any]
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    read: bool = False


class TaskBoard:
    """Shared team task board managing work item lifecycle across subagents."""

    def __init__(self):
        self._tasks: Dict[str, TeamTask] = {}

    def post_task(
        self,
        tenant_id: str,
        assigned_role: str,
        title: str,
        payload: Dict[str, Any],
    ) -> TeamTask:
        task = TeamTask(
            task_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            assigned_role=assigned_role,
            title=title,
            status="pending",
            payload=payload,
        )
        self._tasks[task.task_id] = task
        return task

    def claim_task(self, task_id: str, agent_name: str) -> TeamTask:
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found on board")
        task.status = "claimed"
        task.assigned_agent = agent_name
        return task

    def complete_task(self, task_id: str, result: Dict[str, Any]) -> TeamTask:
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found on board")
        task.status = "completed"
        task.result = result
        task.completed_at = datetime.now(timezone.utc)
        return task

    def fail_task(self, task_id: str, error: str) -> TeamTask:
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found on board")
        task.status = "failed"
        task.result = {"error": error}
        task.completed_at = datetime.now(timezone.utc)
        return task

    def list_tasks(
        self,
        tenant_id: str,
        role: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[TeamTask]:
        tasks = [t for t in self._tasks.values() if t.tenant_id == tenant_id]
        if role:
            tasks = [t for t in tasks if t.assigned_role == role]
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks


class AgentMailbox:
    """Inter-agent messaging system for subagent coordination and handoff."""

    def __init__(self):
        self._messages: List[TeamMessage] = []

    def send(
        self,
        tenant_id: str,
        sender_role: str,
        recipient_role: str,
        subject: str,
        payload: Dict[str, Any],
    ) -> TeamMessage:
        msg = TeamMessage(
            message_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            sender_role=sender_role,
            recipient_role=recipient_role,
            subject=subject,
            payload=payload,
        )
        self._messages.append(msg)
        return msg

    def get_inbox(self, tenant_id: str, recipient_role: str) -> List[TeamMessage]:
        return [
            m for m in self._messages
            if m.tenant_id == tenant_id and m.recipient_role == recipient_role
        ]


class CareerAgentTeam:
    """Coordinates Scout -> Analyst -> Tailor -> Reviewer -> Dispatcher agent team."""

    def __init__(self):
        self.board = TaskBoard()
        self.mailbox = AgentMailbox()

    def handoff(
        self,
        tenant_id: str,
        from_role: str,
        to_role: str,
        task_title: str,
        payload: Dict[str, Any],
    ) -> TeamTask:
        """Atomically posts a task to the board and sends a notification message."""
        task = self.board.post_task(
            tenant_id=tenant_id,
            assigned_role=to_role,
            title=task_title,
            payload=payload,
        )
        self.mailbox.send(
            tenant_id=tenant_id,
            sender_role=from_role,
            recipient_role=to_role,
            subject=f"Handoff: {task_title}",
            payload={"task_id": task.task_id, **payload},
        )
        return task


agent_team = CareerAgentTeam()
