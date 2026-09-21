"""Harness Run context & state encapsulation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class AgentAction:
    tool_name: str
    arguments: Dict[str, Any]
    external: bool = False
    match_score: Optional[float] = None


@dataclass
class RunStepResult:
    step_index: int
    tool_name: str
    action_args: Dict[str, Any]
    output: Any
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class RunContext:
    """Represents an active agent execution session."""
    run_id: str
    tenant_id: str
    agent_name: str
    goal: str
    tier: str = "mid"
    status: str = "running"
    step_index: int = 0
    plan: List[str] = field(default_factory=list)
    history: List[RunStepResult] = field(default_factory=list)
    pause_reason: Optional[str] = None
    trusted_mode: bool = False
    daily_auto_applies_used: int = 0

    def trusted_covers(self, action: AgentAction) -> bool:
        """Evaluates whether an external action is pre-authorized by Trusted Mode (D5).

        Trusted Mode rules:
        - Candidate must have enabled Trusted Mode.
        - Match quality must be >= 9.0 / 10.
        - Daily auto-applies must be strictly under the 10/day cap.
        """
        if not self.trusted_mode:
            return False

        if action.match_score is None or action.match_score < 9.0:
            return False

        if self.daily_auto_applies_used >= 10:
            return False

        return True

    def park(self, reason: str = "awaiting_approval") -> "RunContext":
        """Parks the run waiting for human approval or key replenishment."""
        self.status = reason
        self.pause_reason = f"Parked: {reason}"
        return self

    def record_step(self, tool_name: str, args: Dict[str, Any], output: Any) -> None:
        """Records step execution and increments counter."""
        self.history.append(
            RunStepResult(
                step_index=self.step_index,
                tool_name=tool_name,
                action_args=args,
                output=output,
            )
        )
        self.step_index += 1
