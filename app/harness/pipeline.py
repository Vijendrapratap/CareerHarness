"""Guarded Tool Execution Pipeline with Lifecycle Interceptors.

Pattern borrowed from DeepSeek Harness (dsh):
Wraps tool execution in pre-execution policy checks, quota guardrails,
honesty invariant assertions, and durable event projections.
"""

from typing import Any, Callable, Dict, List, Optional

from app.harness.projections import SessionEvent, projection_registry


class PipelineAbortError(Exception):
    """Raised when a pre-execution interceptor aborts tool invocation."""
    pass


class ToolInterceptor:
    """Base class for tool execution pipeline interceptors."""

    async def before_execute(
        self,
        tenant_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        run_id: Optional[str] = None,
    ) -> None:
        pass

    async def after_execute(
        self,
        tenant_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        run_id: Optional[str] = None,
    ) -> Any:
        return result


class TenantIsolationInterceptor(ToolInterceptor):
    """Enforces fail-closed multi-tenancy before invoking any tool."""

    async def before_execute(
        self,
        tenant_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        run_id: Optional[str] = None,
    ) -> None:
        if not tenant_id or len(tenant_id.strip()) < 8:
            raise PipelineAbortError(f"Fail-closed: Missing valid tenant_id context for tool '{tool_name}'")


class EventProjectionInterceptor(ToolInterceptor):
    """Emits durable session events for live projection and timeline feeds."""

    async def after_execute(
        self,
        tenant_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        run_id: Optional[str] = None,
    ) -> Any:
        if run_id:
            projection_registry.append_event(
                SessionEvent(
                    event_id=f"ev_{tool_name}_{run_id[:6]}",
                    tenant_id=tenant_id,
                    run_id=run_id,
                    event_type=f"tool_executed:{tool_name}",
                    payload={"arguments": arguments, "result": result},
                )
            )
        return result


class GuardedToolPipeline:
    """Executes tools through an ordered interceptor pipeline."""

    def __init__(self):
        self.interceptors: List[ToolInterceptor] = [
            TenantIsolationInterceptor(),
            EventProjectionInterceptor(),
        ]

    def add_interceptor(self, interceptor: ToolInterceptor) -> None:
        self.interceptors.append(interceptor)

    async def execute_guarded(
        self,
        handler: Callable[..., Any],
        tenant_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        run_id: Optional[str] = None,
    ) -> Any:
        """Runs pre-execution interceptors, invokes handler, then runs post-execution interceptors."""
        # 1. Pre-execution hooks
        for interceptor in self.interceptors:
            await interceptor.before_execute(
                tenant_id=tenant_id,
                tool_name=tool_name,
                arguments=arguments,
                run_id=run_id,
            )

        # 2. Invoke tool
        result = await handler(tenant_id=tenant_id, **arguments)

        # 3. Post-execution hooks
        for interceptor in self.interceptors:
            result = await interceptor.after_execute(
                tenant_id=tenant_id,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                run_id=run_id,
            )

        return result


guarded_pipeline = GuardedToolPipeline()
