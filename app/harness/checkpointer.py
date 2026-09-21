"""PostgreSQL Checkpointer for agent state snapshotting and crash-resume recovery."""

from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Checkpoint, Run
from app.harness.run import RunContext, RunStepResult


class Checkpointer:
    """Manages saving and restoring Run checkpoints in PostgreSQL."""

    @staticmethod
    async def save_checkpoint(
        session: AsyncSession,
        run: RunContext,
    ) -> Checkpoint:
        """Serializes current Run state into a database Checkpoint row."""
        snapshot = {
            "run_id": run.run_id,
            "tenant_id": run.tenant_id,
            "agent_name": run.agent_name,
            "goal": run.goal,
            "tier": run.tier,
            "status": run.status,
            "step_index": run.step_index,
            "plan": run.plan,
            "trusted_mode": run.trusted_mode,
            "daily_auto_applies_used": run.daily_auto_applies_used,
            "observations": run.observations,
            "reflections": run.reflections,
            "history": [
                {
                    "step_index": h.step_index,
                    "tool_name": h.tool_name,
                    "action_args": h.action_args,
                    "output": h.output,
                    "timestamp": h.timestamp,
                }
                for h in run.history
            ],
        }

        checkpoint = Checkpoint(
            tenant_id=run.tenant_id,
            run_id=run.run_id,
            step_index=run.step_index,
            state_snapshot=snapshot,
        )
        session.add(checkpoint)

        # Update Run table status and step count
        db_run = await session.get(Run, run.run_id)
        if db_run:
            db_run.status = run.status
            db_run.step_count = run.step_index
            db_run.pause_reason = run.pause_reason
            db_run.current_plan = {"steps": run.plan}

        await session.flush()
        return checkpoint

    @staticmethod
    async def restore_run(
        session: AsyncSession,
        run_id: str,
        tenant_id: str,
    ) -> Optional[RunContext]:
        """Restores a Run to its latest checkpoint state following a worker restart."""
        query = (
            select(Checkpoint)
            .where(Checkpoint.run_id == run_id, Checkpoint.tenant_id == tenant_id)
            .order_by(desc(Checkpoint.step_index))
            .limit(1)
        )
        result = await session.execute(query)
        cp = result.scalar_one_or_none()

        if not cp:
            # Fall back to base Run row if no checkpoint exists yet
            db_run = await session.get(Run, run_id)
            if not db_run or db_run.tenant_id != tenant_id:
                return None
            return RunContext(
                run_id=db_run.id,
                tenant_id=db_run.tenant_id,
                agent_name=db_run.agent_name,
                goal=db_run.goal,
                status=db_run.status,
                step_index=db_run.step_count,
            )

        snap = cp.state_snapshot
        history = [
            RunStepResult(
                step_index=item["step_index"],
                tool_name=item["tool_name"],
                action_args=item["action_args"],
                output=item["output"],
                timestamp=item.get("timestamp", ""),
            )
            for item in snap.get("history", [])
        ]

        return RunContext(
            run_id=snap["run_id"],
            tenant_id=snap["tenant_id"],
            agent_name=snap["agent_name"],
            goal=snap["goal"],
            tier=snap.get("tier", "mid"),
            status=snap.get("status", "running"),
            step_index=snap.get("step_index", 0),
            plan=snap.get("plan", []),
            history=history,
            trusted_mode=snap.get("trusted_mode", False),
            daily_auto_applies_used=snap.get("daily_auto_applies_used", 0),
            observations=snap.get("observations", []),
            reflections=snap.get("reflections", []),
        )


checkpointer = Checkpointer()
