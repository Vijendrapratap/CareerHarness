"""The Thin Agent Loop (plan -> act -> observe -> reflect -> checkpoint)."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keyvault import keyvault
from app.core.model_router import router
from app.domain.memory import memory
from app.harness.checkpointer import checkpointer
from app.harness.gate import gate
from app.harness.registry import registry
from app.harness.run import AgentAction, RunContext


class AgentLoop:
    """Core execution engine for CareerHarness agents (~3k LOC target)."""

    @staticmethod
    async def step(
        session: AsyncSession,
        run: RunContext,
        provider: str = "openai",
        action_override: Optional[AgentAction] = None,
    ) -> RunContext:
        """Executes a single step in the agent's plan loop."""
        # 1. Budgeted memory context fetch [fail-closed]
        ctx = memory.retrieve(
            tenant_id=run.tenant_id,
            view_spec=["profile", "roles", "verified_skills", "resume_bullets"],
        )

        # 2. BYOK API key decryption in worker memory only
        raw_key = await keyvault.get_decrypted_key(
            session=session,
            tenant_id=run.tenant_id,
            provider=provider,
        )

        # 3. Determine action (from override or model router inference)
        if action_override:
            action = action_override
        else:
            # Model inference step
            _ = await router.call(
                provider=provider,
                raw_key=raw_key,
                tier=run.tier,  # type: ignore
                system_prompt=f"You are agent '{run.agent_name}'. Goal: {run.goal}",
                messages=[{"role": "user", "content": f"Context: {ctx}"}],
            )
            # Default internal blackboard step if no specific action provided
            action = AgentAction(
                tool_name="blackboard_read",
                arguments={"view_spec": ["profile", "roles"]},
                external=False,
            )

        # 4. Check tool registry and permissions
        tool = registry.get(action.tool_name)
        action.external = tool.meta.external

        # 5. Gate Middleware: External actions convert to approval rows unless covered by Trusted Mode
        if action.external and not run.trusted_covers(action):
            await gate.propose_action(session=session, run=run, action=action)
            return run

        # 6. Execute action
        output = await tool.execute(tenant_id=run.tenant_id, **action.arguments)

        # Track auto-apply quota if executed under Trusted Mode
        if action.external and run.trusted_covers(action):
            run.daily_auto_applies_used += 1

        # 7. Record step and update plan
        run.record_step(tool_name=action.tool_name, args=action.arguments, output=output)

        # 8. Checkpoint execution state
        await checkpointer.save_checkpoint(session=session, run=run)
        return run


agent_loop = AgentLoop()
