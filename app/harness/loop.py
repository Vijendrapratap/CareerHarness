"""The Thin Agent Loop (plan -> act -> observe -> reflect -> checkpoint)."""

from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keyvault import KeyInactiveError, KeyNotFoundError, keyvault
from app.core.model_router import KeyExhaustedError, router
from app.domain.memory import memory
from app.domain.models import OutboxEvent
from app.harness.checkpointer import checkpointer
from app.harness.gate import gate
from app.harness.pipeline import guarded_pipeline
from app.harness.registry import registry
from app.harness.run import AgentAction, RunContext


class AgentLoop:
    """Core execution engine for CareerHarness agents (~3k LOC target) using DeepSeek 5-stage loop."""

    @staticmethod
    async def reflect(
        session: AsyncSession,
        run: RunContext,
        action: AgentAction,
        observation: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Reflect on tool output against invariants, goals, and domain constraints."""
        status = observation.get("status", "success")
        output = observation.get("output")
        needs_correction = False
        correction_reason = ""

        # Reflection Invariant 1: Check for tool failures or exceptions
        if status == "error" or isinstance(output, Exception):
            needs_correction = True
            correction_reason = f"Tool {action.tool_name} failed: {output}"

        # Reflection Invariant 2: Check for domain hallucination / empty output in critical steps
        elif action.tool_name == "resume_tailor" and isinstance(output, dict):
            if not output.get("tailored_bullets"):
                needs_correction = True
                correction_reason = "Tailored resume produced zero bullets; regenerate with master experience."

        reflection = {
            "step_index": run.step_index,
            "tool_name": action.tool_name,
            "success": not needs_correction,
            "needs_correction": needs_correction,
            "correction_reason": correction_reason,
            "next_action": "retry" if needs_correction else "continue",
        }
        return reflection

    @staticmethod
    async def step(
        session: AsyncSession,
        run: RunContext,
        provider: str = "openai",
        action_override: Optional[AgentAction] = None,
    ) -> RunContext:
        """Executes a single 5-stage step: Plan -> Act -> Observe -> Reflect -> Checkpoint."""
        # 1. PLAN: Retrieve budgeted memory context and check provider credentials
        ctx = memory.retrieve(
            tenant_id=run.tenant_id,
            view_spec=["profile", "roles", "verified_skills", "resume_bullets"],
        )

        try:
            raw_key = await keyvault.get_decrypted_key(
                session=session,
                tenant_id=run.tenant_id,
                provider=provider,
            )
        except (KeyNotFoundError, KeyInactiveError) as e:
            # Park run due to inactive or missing BYOK key
            run.park("no_credits")
            run.pause_reason = f"Provider key unavailable: {str(e)}"
            await checkpointer.save_checkpoint(session=session, run=run)
            return run

        # 2. ACT: Select and dispatch action
        if action_override:
            action = action_override
        else:
            try:
                # Include reflections in system prompt if previous step needed correction
                system_prompt = f"You are agent '{run.agent_name}'. Goal: {run.goal}"
                if run.reflections and run.reflections[-1].get("needs_correction"):
                    system_prompt += f" SYSTEM CORRECTION: {run.reflections[-1].get('correction_reason')}"

                _ = await router.call(
                    provider=provider,
                    raw_key=raw_key,
                    tier=run.tier,  # type: ignore
                    system_prompt=system_prompt,
                    messages=[{"role": "user", "content": f"Context: {ctx}"}],
                )
                action = AgentAction(
                    tool_name="blackboard_read",
                    arguments={"view_spec": ["profile", "roles"]},
                    external=False,
                )
            except KeyExhaustedError as e:
                # BYOK quota exhausted: fail closed, mark key no_credits, park run, zero platform fallback
                await keyvault.handle_key_failure(
                    session=session,
                    tenant_id=run.tenant_id,
                    provider=provider,
                    reason=f"Quota exhausted: {str(e)}",
                )
                run.park("no_credits")
                run.pause_reason = f"Provider key credit exhausted: {str(e)}"
                session.add(
                    OutboxEvent(
                        tenant_id=run.tenant_id,
                        event_name="key.exhausted",
                        payload={"provider": provider, "run_id": run.run_id, "error": str(e)},
                    )
                )
                await checkpointer.save_checkpoint(session=session, run=run)
                return run

        # Tool registry check
        tool = registry.get(action.tool_name)
        action.external = tool.meta.external

        # Gate check: external actions require Trusted Mode or park for human approval
        if action.external and not run.trusted_covers(action):
            await gate.propose_action(session=session, run=run, action=action)
            return run

        # Execute through guarded pipeline
        try:
            output = await guarded_pipeline.execute_guarded(
                handler=tool.execute,
                tenant_id=run.tenant_id,
                tool_name=action.tool_name,
                arguments=action.arguments,
                run_id=run.run_id,
            )
            step_status = "success"
        except Exception as exc:
            output = exc
            step_status = "error"

        # Auto-apply quota tracking
        if action.external and run.trusted_covers(action) and step_status == "success":
            run.daily_auto_applies_used += 1

        # 3. OBSERVE: Capture observation
        obs = {
            "step_index": run.step_index,
            "tool_name": action.tool_name,
            "arguments": action.arguments,
            "output": str(output) if isinstance(output, Exception) else output,
            "status": step_status,
        }
        run.add_observation(obs)

        # 4. REFLECT: Evaluate observation against domain invariants
        reflection = await AgentLoop.reflect(
            session=session,
            run=run,
            action=action,
            observation=obs,
        )
        run.add_reflection(reflection)

        # 5. CHECKPOINT: Record history and persist checkpoint
        run.record_step(tool_name=action.tool_name, args=action.arguments, output=output)
        await checkpointer.save_checkpoint(session=session, run=run)
        return run


agent_loop = AgentLoop()
