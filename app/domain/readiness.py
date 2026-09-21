"""Readiness Gate Evaluator & Scout Scheduler Guard (F7, RD-01)."""

from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import ReadinessScore, TodoItem


class ReadinessGateBlockedError(Exception):
    """Raised when an automated scout or application action is attempted before clearing the gate (RD-01)."""
    pass


@dataclass
class ReadinessStatus:
    is_ready: bool
    overall_score: int
    open_criticals: int
    is_capped: bool
    cap_reason: Optional[str]
    unblocking_todos: List[Dict[str, str]]


class ReadinessGateService:
    """Enforces the Front-Face Readiness Gate (70+ score AND zero open criticals)."""

    @staticmethod
    async def evaluate_readiness(
        session: AsyncSession,
        tenant_id: str,
    ) -> ReadinessStatus:
        """Evaluates whether the candidate's front face passes the gate to unlock automated scouting."""
        # 1. Fetch latest score
        score_q = (
            select(ReadinessScore)
            .where(ReadinessScore.tenant_id == tenant_id)
            .order_by(desc(ReadinessScore.created_at))
            .limit(1)
        )
        score_rec = (await session.execute(score_q)).scalar_one_or_none()
        current_score = score_rec.overall_score if score_rec else 0
        is_capped = score_rec.is_capped_at_69 if score_rec else False
        cap_reason = score_rec.cap_reason if score_rec else None

        # 2. Count open criticals
        critical_q = select(TodoItem).where(
            TodoItem.tenant_id == tenant_id,
            TodoItem.severity == "critical",
            TodoItem.status == "open",
        )
        open_critical_recs = (await session.execute(critical_q)).scalars().all()
        open_criticals = len(open_critical_recs)

        # Gate pass condition: score >= 70 AND 0 open criticals
        is_ready = (current_score >= 70) and (open_criticals == 0)

        # Extract up to 3 highest leverage unblocking tasks
        unblocking = [
            {
                "id": t.id,
                "category": t.category,
                "issue": t.issue_text,
                "fix_draft": t.fix_draft,
            }
            for t in open_critical_recs[:3]
        ]

        return ReadinessStatus(
            is_ready=is_ready,
            overall_score=current_score,
            open_criticals=open_criticals,
            is_capped=is_capped,
            cap_reason=cap_reason,
            unblocking_todos=unblocking,
        )

    @staticmethod
    async def verify_can_schedule_scout(
        session: AsyncSession,
        tenant_id: str,
    ) -> bool:
        """Enforces RD-01: Scout is unschedulable below threshold."""
        status = await ReadinessGateService.evaluate_readiness(session, tenant_id)
        if not status.is_ready:
            raise ReadinessGateBlockedError(
                f"Readiness Gate Locked: Current Front-Face Score is {status.overall_score}/100 with "
                f"{status.open_criticals} open critical item(s). Minimum 70 score and 0 criticals required."
            )
        return True


readiness_gate = ReadinessGateService()
