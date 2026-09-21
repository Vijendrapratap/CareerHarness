"""Session Event Projection Seam.

Pattern borrowed from DeepSeek Harness (dsh):
Pure message and event projection seam (dsh-session-projection) that folds
immutable attempt streams and session events incrementally into a typed live
execution state, candidate activity timeline, and UI snapshots.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class SessionEvent:
    event_id: str
    tenant_id: str
    run_id: str
    event_type: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class LiveRunProjection:
    run_id: str
    tenant_id: str
    current_phase: str
    status: str
    step_count: int
    tailored_keywords: List[str]
    honesty_passed: bool
    ats_score: Optional[int]
    active_bot_tier: int
    is_awaiting_approval: bool
    timeline: List[Dict[str, Any]]
    completed_at: Optional[datetime] = None


class SessionProjectionRegistry:
    """Projection engine folding durable session events into live typed views."""

    def __init__(self):
        self._events: Dict[str, List[SessionEvent]] = {}

    def append_event(self, event: SessionEvent) -> None:
        if event.run_id not in self._events:
            self._events[event.run_id] = []
        self._events[event.run_id].append(event)

    def state_of(self, run_id: str) -> LiveRunProjection:
        """Folds committed events incrementally to derive pure state of a run."""
        events = self._events.get(run_id, [])
        if not events:
            return LiveRunProjection(
                run_id=run_id,
                tenant_id="",
                current_phase="INIT",
                status="pending",
                step_count=0,
                tailored_keywords=[],
                honesty_passed=True,
                ats_score=None,
                active_bot_tier=1,
                is_awaiting_approval=False,
                timeline=[],
            )

        tenant_id = events[0].tenant_id
        current_phase = "INITIALIZED"
        status = "running"
        step_count = 0
        tailored_keywords: List[str] = []
        honesty_passed = True
        ats_score: Optional[int] = None
        active_bot_tier = 1
        is_awaiting_approval = False
        timeline: List[Dict[str, Any]] = []
        completed_at: Optional[datetime] = None

        for ev in events:
            step_count += 1
            entry = {
                "event_type": ev.event_type,
                "timestamp": ev.timestamp.isoformat(),
                "details": ev.payload,
            }
            timeline.append(entry)

            if ev.event_type == "turn_start":
                current_phase = "PLANNING"

            elif ev.event_type == "tailoring_completed":
                current_phase = "TAILORED"
                tailored_keywords = ev.payload.get("keywords", [])

            elif ev.event_type == "honesty_review_passed":
                current_phase = "REVIEW_PASSED"
                honesty_passed = True

            elif ev.event_type == "honesty_review_failed":
                current_phase = "REVIEW_FAILED"
                honesty_passed = False
                status = "failed"

            elif ev.event_type == "ats_check_completed":
                current_phase = "ATS_VERIFIED"
                ats_score = ev.payload.get("ats_score")

            elif ev.event_type == "gate_interception":
                current_phase = "AWAITING_APPROVAL"
                is_awaiting_approval = True
                status = "awaiting_approval"

            elif ev.event_type == "gate_approved":
                is_awaiting_approval = False
                status = "running"

            elif ev.event_type == "bot_block_detected":
                current_phase = "FALLBACK_ESCALATION"
                active_bot_tier = ev.payload.get("next_tier", active_bot_tier + 1)

            elif ev.event_type == "submission_settled":
                current_phase = "COMPLETED"
                status = "completed"
                active_bot_tier = ev.payload.get("tier", active_bot_tier)
                completed_at = ev.timestamp

        return LiveRunProjection(
            run_id=run_id,
            tenant_id=tenant_id,
            current_phase=current_phase,
            status=status,
            step_count=step_count,
            tailored_keywords=tailored_keywords,
            honesty_passed=honesty_passed,
            ats_score=ats_score,
            active_bot_tier=active_bot_tier,
            is_awaiting_approval=is_awaiting_approval,
            timeline=timeline,
            completed_at=completed_at,
        )

    def snapshot(self, run_id: str) -> Dict[str, Any]:
        """Provides a client-facing UI snapshot of the run."""
        state = self.state_of(run_id)
        return {
            "run_id": state.run_id,
            "phase": state.current_phase,
            "status": state.status,
            "steps": state.step_count,
            "injected_keywords": state.tailored_keywords,
            "honesty_audit": "passed" if state.honesty_passed else "failed",
            "ats_compatibility_score": state.ats_score,
            "mitigation_tier": state.active_bot_tier,
            "requires_human_gate": state.is_awaiting_approval,
            "timeline_events_count": len(state.timeline),
        }


projection_registry = SessionProjectionRegistry()
