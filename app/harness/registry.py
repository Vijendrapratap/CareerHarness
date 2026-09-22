"""Scoped Tool Registry with External Permission & Gate Gating."""

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, List


class ToolPermissionError(Exception):
    """Raised when an agent attempts to invoke a tool outside its allowed scope."""
    pass


@dataclass
class ToolMetadata:
    name: str
    description: str
    permission_scope: str
    external: bool = False
    gate_required: bool = False


class Tool:
    def __init__(self, meta: ToolMetadata, handler: Callable[..., Any]):
        self.meta = meta
        self.handler = handler

    async def execute(self, tenant_id: str, **kwargs: Any) -> Any:
        """Executes the tool handler, injecting tenant_id context."""
        if not tenant_id:
            raise ToolPermissionError("Execution denied: tenant_id context missing.")

        sig = inspect.signature(self.handler)
        if "tenant_id" in sig.parameters:
            kwargs["tenant_id"] = tenant_id

        if inspect.iscoroutinefunction(self.handler):
            return await self.handler(**kwargs)
        return self.handler(**kwargs)


class ToolRegistry:
    """Registry containing agent tool declarations."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.meta.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Tool not registered: '{name}'")
        return self._tools[name]

    def list_tools(self) -> List[ToolMetadata]:
        return [t.meta for t in self._tools.values()]


# Default harness registry instance
registry = ToolRegistry()


# Register baseline tools
def _read_memory(tenant_id: str, view_spec: List[str]) -> Dict[str, Any]:
    from app.domain.memory import memory
    return memory.retrieve(tenant_id=tenant_id, view_spec=view_spec)


def _write_memory(tenant_id: str, section: str, data: Any) -> Dict[str, Any]:
    from app.domain.memory import memory
    memory.write_section(tenant_id=tenant_id, section=section, data=data)
    return {"status": "written", "section": section}


async def _ats_submit(tenant_id: str, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    # External submission handler
    return {"status": "submitted", "channel": "ats", "job_id": job_id}


async def _outreach_send(tenant_id: str, recipient: str, subject: str, body: str) -> Dict[str, Any]:
    # External email send handler
    return {"status": "sent", "channel": "email", "recipient": recipient}


registry.register(
    Tool(
        meta=ToolMetadata(
            name="blackboard_read",
            description="Reads candidate profile, skills, and resume data slices.",
            permission_scope="read:blackboard",
            external=False,
            gate_required=False,
        ),
        handler=_read_memory,
    )
)

registry.register(
    Tool(
        meta=ToolMetadata(
            name="blackboard_write",
            description="Updates candidate resume bullets or fix drafts.",
            permission_scope="write:blackboard",
            external=False,
            gate_required=False,
        ),
        handler=_write_memory,
    )
)

registry.register(
    Tool(
        meta=ToolMetadata(
            name="ats_apply",
            description="Submits tailored job application to an external ATS portal.",
            permission_scope="apply:ats",
            external=True,
            gate_required=True,
        ),
        handler=_ats_submit,
    )
)

registry.register(
    Tool(
        meta=ToolMetadata(
            name="outreach_email_send",
            description="Sends outreach email to a hiring manager via connected mailbox.",
            permission_scope="send:email",
            external=True,
            gate_required=True,
        ),
        handler=_outreach_send,
    )
)

async def _tool_connect_mailbox(tenant_id: str, email_address: str, access_token: str, refresh_token: str, provider: str = "gmail", **kwargs):
    from app.core.database import async_session_factory
    from app.mcp.tools import connect_mailbox
    async with async_session_factory() as session:
        return await connect_mailbox(tenant_id=tenant_id, session=session, email_address=email_address, access_token=access_token, refresh_token=refresh_token, provider=provider)

async def _tool_grant_send_consent(tenant_id: str, **kwargs):
    from app.core.database import async_session_factory
    from app.mcp.tools import grant_send_consent
    async with async_session_factory() as session:
        return await grant_send_consent(tenant_id=tenant_id, session=session)

async def _tool_queue_recruiter_email(tenant_id: str, recipient: str, subject: str, body: str, **kwargs):
    from app.core.database import async_session_factory
    from app.mcp.tools import queue_recruiter_email
    async with async_session_factory() as session:
        return await queue_recruiter_email(tenant_id=tenant_id, session=session, recipient=recipient, subject=subject, body=body)

registry.register(
    Tool(
        meta=ToolMetadata(
            name="connect_mailbox",
            description="Connects candidate's mailbox with OAuth credentials.",
            permission_scope="connect:mailbox",
            external=False,
            gate_required=False,
        ),
        handler=_tool_connect_mailbox,
    )
)

registry.register(
    Tool(
        meta=ToolMetadata(
            name="grant_send_consent",
            description="Grants explicit outreach email consent.",
            permission_scope="consent:outreach",
            external=False,
            gate_required=False,
        ),
        handler=_tool_grant_send_consent,
    )
)

registry.register(
    Tool(
        meta=ToolMetadata(
            name="queue_recruiter_email",
            description="Queues an outreach email to a recruiter from the posting.",
            permission_scope="send:recruiter",
            external=True,
            gate_required=True,
        ),
        handler=_tool_queue_recruiter_email,
    )
)

