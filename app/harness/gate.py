"""Human-in-the-Loop (HITL) Approval Gate Middleware."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import outbox
from app.domain.models import Approval, Run
from app.harness.checkpointer import checkpointer
from app.harness.run import AgentAction, RunContext


class ApprovalGateMiddleware:
    """Intercepts external actions and gates them behind human consent (D5)."""

    @staticmethod
    async def propose_action(
        session: AsyncSession,
        run: RunContext,
        action: AgentAction,
    ) -> Approval:
        """Parks the run and logs an Approval record for human confirmation."""
        approval = Approval(
            id=str(uuid.uuid4()),
            tenant_id=run.tenant_id,
            run_id=run.run_id,
            tool_name=action.tool_name,
            action_type="external_action",
            payload=action.arguments,
            status="pending",
        )
        session.add(approval)

        # Park the run
        run.park("awaiting_approval")
        await checkpointer.save_checkpoint(session, run)

        # Emit event to notify UI / user
        await outbox.record_event(
            session=session,
            tenant_id=run.tenant_id,
            event_name="run.parked",
            payload={
                "run_id": run.run_id,
                "approval_id": approval.id,
                "tool_name": action.tool_name,
                "arguments": action.arguments,
            },
        )
        await session.flush()
        return approval

    @staticmethod
    async def resolve_approval(
        session: AsyncSession,
        approval_id: str,
        tenant_id: str,
        approved: bool,
    ) -> Approval:
        """Resolves an approval and un-parks the run if approved."""
        query = select(Approval).where(
            Approval.id == approval_id,
            Approval.tenant_id == tenant_id,
        )
        result = await session.execute(query)
        approval = result.scalar_one_or_none()

        if not approval:
            raise ValueError(f"Approval '{approval_id}' not found for tenant '{tenant_id}'")

        now = datetime.now(timezone.utc)
        approval.status = "approved" if approved else "rejected"
        approval.resolved_at = now

        db_run = await session.get(Run, approval.run_id)
        if db_run and db_run.tenant_id == tenant_id:
            if approved:
                db_run.status = "running"
                db_run.pause_reason = None
            else:
                db_run.status = "completed"
                db_run.pause_reason = "Action rejected by user"

        await session.flush()
        return approval


gate = ApprovalGateMiddleware()
