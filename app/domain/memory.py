"""Blackboard Memory Tools & Token Context Budgeter.

Provides the only read/write path to candidate career data for agent runs.
Fails-closed without valid tenant context.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


class MemoryAccessError(Exception):
    """Raised on invalid memory access or tenant context violation."""
    pass


@dataclass
class BlackboardData:
    profile: Dict[str, Any] = field(default_factory=dict)
    roles: List[Dict[str, Any]] = field(default_factory=list)
    verified_skills: List[str] = field(default_factory=list)
    resume_bullets: List[Dict[str, Any]] = field(default_factory=list)
    todo_fixes: List[Dict[str, Any]] = field(default_factory=list)
    active_jobs: List[Dict[str, Any]] = field(default_factory=list)


class ContextBudgeter:
    """Budgets and compresses slices of the blackboard graph to prevent context overflow."""

    @staticmethod
    def budget_slice(data: Dict[str, Any], max_char_limit: int = 4000) -> Dict[str, Any]:
        """Compresses graph slices to fit within the per-step token cap."""
        budgeted: Dict[str, Any] = {}
        current_len = 0

        for key, val in data.items():
            val_str = str(val)
            if current_len + len(val_str) > max_char_limit:
                # Truncate large lists or text slices
                if isinstance(val, list):
                    budgeted[key] = val[:3]  # keep top 3 entries
                elif isinstance(val, str):
                    budgeted[key] = val[:500] + "... [budget truncated]"
                else:
                    budgeted[key] = "[budget truncated]"
            else:
                budgeted[key] = val
                current_len += len(val_str)

        return budgeted


class BlackboardMemory:
    """Per-tenant isolated blackboard store."""

    def __init__(self):
        # In-memory per-tenant blackboard store for fast agent retrieval
        self._stores: Dict[str, BlackboardData] = {}

    def _get_store(self, tenant_id: str) -> BlackboardData:
        if not tenant_id:
            raise MemoryAccessError("Tenant ID is required for blackboard access (Fail-Closed).")
        if tenant_id not in self._stores:
            self._stores[tenant_id] = BlackboardData()
        return self._stores[tenant_id]

    def retrieve(
        self,
        tenant_id: str,
        view_spec: List[str],
        max_chars: int = 4000,
    ) -> Dict[str, Any]:
        """Fail-closed retrieval of budgeted blackboard data slices."""
        store = self._get_store(tenant_id)
        raw_slice: Dict[str, Any] = {}

        for spec in view_spec:
            if hasattr(store, spec):
                raw_slice[spec] = getattr(store, spec)

        return ContextBudgeter.budget_slice(raw_slice, max_char_limit=max_chars)

    def write_section(
        self,
        tenant_id: str,
        section: str,
        data: Any,
    ) -> None:
        """Writes verified domain data to the candidate's blackboard."""
        store = self._get_store(tenant_id)
        if hasattr(store, section):
            setattr(store, section, data)
        else:
            raise MemoryAccessError(f"Invalid blackboard section: {section}")


memory = BlackboardMemory()
