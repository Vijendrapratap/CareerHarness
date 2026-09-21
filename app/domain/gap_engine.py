"""Gap Engine, Front-Face Scoring (0–100), and To-Do Fix Generator (F5, GE-01..05)."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import outbox
from app.domain.models import (
    GapReport,
    LinkedInProfile,
    ReadinessScore,
    ResumeParse,
    TodoItem,
)
from app.domain.roles import roles_service


class GapEngineError(Exception):
    pass


class GapEngine:
    """Computes presentation vs honest skill gaps and calculates candidate Front-Face Score."""

    @staticmethod
    def calculate_raw_score(
        ats_parse: int,
        metric_coverage: int,
        honest_keywords: int,
        linkedin_headline_about: int,
        experience_mirroring: int,
        critical_todos_cleared: int,
    ) -> int:
        """Computes sum of 6 Front-Face components (max 100)."""
        raw = (
            min(15, ats_parse)
            + min(20, metric_coverage)
            + min(15, honest_keywords)
            + min(20, linkedin_headline_about)
            + min(15, experience_mirroring)
            + min(15, critical_todos_cleared)
        )
        return max(0, min(100, raw))

    @staticmethod
    async def compute_gaps(
        session: AsyncSession,
        tenant_id: str,
    ) -> Tuple[GapReport, List[TodoItem], ReadinessScore]:
        """Runs the two-way comparison (Resume↔Roles, LinkedIn↔Resume) and computes Front-Face Score."""
        # 1. Fetch assets
        roles = await roles_service.get_selected_roles(session, tenant_id)
        if not roles:
            raise GapEngineError("Cannot compute gaps: No target roles selected.")

        priority_role = roles[0]
        role_def = roles_service.find_role_in_catalog(priority_role.role_id)
        baseline_skills = role_def.get("baseline_skills", []) if role_def else []

        resume_q = (
            select(ResumeParse)
            .where(ResumeParse.tenant_id == tenant_id)
            .order_by(desc(ResumeParse.created_at))
            .limit(1)
        )
        resume = (await session.execute(resume_q)).scalar_one_or_none()

        linkedin_q = (
            select(LinkedInProfile)
            .where(LinkedInProfile.tenant_id == tenant_id)
            .order_by(desc(LinkedInProfile.created_at))
            .limit(1)
        )
        linkedin = (await session.execute(linkedin_q)).scalar_one_or_none()

        # 2. Extract verified skills and source bullets
        verified_skills: List[str] = []
        bullets: List[str] = []
        metrics_found = 0

        if resume:
            verified_skills = [
                s["name"] for s in resume.extracted_skills if s.get("verified") is True
            ]
            bullets = resume.sections.get("bullets", [])
            metrics_found = len(resume.metrics)

        # 3. Generate To-Do items with GE-01 (Source citation) and GE-02 (No invented skills)
        existing_todos_q = select(TodoItem).where(
            TodoItem.tenant_id == tenant_id,
            TodoItem.status.in_(["accepted", "dismissed"]),
        )
        resolved_todos = (await session.execute(existing_todos_q)).scalars().all()
        resolved_issue_keys = {t.issue_text for t in resolved_todos}

        # Clean up prior unaccepted open todos to prevent accumulation
        await session.execute(
            delete(TodoItem).where(
                TodoItem.tenant_id == tenant_id,
                TodoItem.status == "open",
            )
        )

        todo_items: List[TodoItem] = []
        presentation_gaps: List[Dict[str, Any]] = []
        skill_gaps: List[Dict[str, Any]] = []
        linkedin_gaps: List[Dict[str, Any]] = []

        def add_todo_if_new(todo: TodoItem):
            if todo.issue_text not in resolved_issue_keys:
                todo_items.append(todo)

        # Check: Missing metrics in resume bullets (Presentation gap)
        for bullet in bullets:
            has_metric = any(c in bullet for c in ["%", "$", "k", "M", "x", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])
            if not has_metric:
                presentation_gaps.append({"bullet": bullet, "issue": "Missing quantifiable impact metric"})
                # Fix draft MUST cite source bullet (GE-01) and use confirm chip for unverified metric
                todo = TodoItem(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    category="resume_bullet",
                    severity="major",
                    issue_text=f"Bullet lacks quantifiable metrics: '{bullet[:60]}...'",
                    why_it_matters="Recruiters and ATS favor quantifiable results over generic task lists.",
                    fix_draft=f"{bullet} [confirm: increased efficiency by 25%].",
                    source_bullet=bullet,  # GE-01 Citability
                    has_unverified_metric=True,
                    status="open",
                )
                add_todo_if_new(todo)

        # Check: Missing baseline skills (Honest skill gaps)
        for req_skill in baseline_skills:
            if req_skill not in verified_skills:
                skill_gaps.append({"skill": req_skill, "issue": "Required baseline skill not verified"})
                todo = TodoItem(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    category="skill_alignment",
                    severity="critical",
                    issue_text=f"Target role '{priority_role.title}' expects skill '{req_skill}'.",
                    why_it_matters="ATS screening filters heavily weight baseline core competencies.",
                    # GE-02: Fix draft frames skill honestly without inventing experiences
                    fix_draft=f"Confirm if you have practical experience with {req_skill} to add to verified skills.",
                    source_bullet=None,
                    status="open",
                )
                add_todo_if_new(todo)

        # Check: LinkedIn headline keyword alignment
        if linkedin:
            headline_lower = linkedin.headline.lower()
            role_keywords = [w.lower() for w in priority_role.title.split() if len(w) > 3]
            keyword_match = any(kw in headline_lower for kw in role_keywords)
            if not keyword_match:
                linkedin_gaps.append({"issue": "LinkedIn headline does not contain target role keywords"})
                todo = TodoItem(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    category="linkedin_headline",
                    severity="critical",
                    issue_text=f"LinkedIn headline does not target '{priority_role.title}'.",
                    why_it_matters="Recruiters search LinkedIn by exact title keywords.",
                    fix_draft=f"{priority_role.title} | {linkedin.headline}",
                    source_bullet=linkedin.headline,  # GE-01 Citability
                    status="open",
                )
                add_todo_if_new(todo)
        else:
            todo = TodoItem(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                category="linkedin_profile",
                severity="critical",
                issue_text="No LinkedIn profile linked yet.",
                why_it_matters="A verified LinkedIn profile completes candidate front-face readiness.",
                fix_draft="Paste or connect your LinkedIn profile.",
                status="open",
            )
            add_todo_if_new(todo)

        # 4. Save Gap Report and Todo Items
        gap_report = GapReport(
            tenant_id=tenant_id,
            presentation_gaps=presentation_gaps,
            skill_gaps=skill_gaps,
            linkedin_gaps=linkedin_gaps,
        )
        session.add(gap_report)
        session.add_all(todo_items)
        await session.flush()

        # 5. Compute Front-Face Score (0–100)
        ats_score = 15 if (resume and resume.confidence_score >= 0.8) else 5
        metric_score = 20 if metrics_found >= 2 else (10 if metrics_found == 1 else 0)
        kw_ratio = (len(verified_skills) / max(1, len(baseline_skills)))
        kw_score = min(15, int(kw_ratio * 15))
        linkedin_score = 20 if (linkedin and len(linkedin.headline) > 10 and len(linkedin_gaps) == 0) else 5
        exp_score = 15 if (resume and len(bullets) >= 3) else 5

        open_criticals = sum(1 for t in todo_items if t.severity == "critical" and t.status == "open")
        criticals_score = 15 if open_criticals == 0 else 0

        raw_total = GapEngine.calculate_raw_score(
            ats_parse=ats_score,
            metric_coverage=metric_score,
            honest_keywords=kw_score,
            linkedin_headline_about=linkedin_score,
            experience_mirroring=exp_score,
            critical_todos_cleared=criticals_score,
        )

        # 6. Check GE-03: Critical-Dismiss Cap Rule
        # If candidate dismisses a critical to-do, score is strictly capped at 69 with explanation
        dismissed_critical_q = select(TodoItem).where(
            TodoItem.tenant_id == tenant_id,
            TodoItem.severity == "critical",
            TodoItem.status == "dismissed",
        )
        dismissed_criticals = (await session.execute(dismissed_critical_q)).scalars().all()

        is_capped = False
        cap_reason = None
        final_score = raw_total

        if dismissed_criticals:
            is_capped = True
            final_score = min(69, raw_total)
            cap_reason = (
                f"Score capped at 69: Candidate dismissed {len(dismissed_criticals)} critical "
                f"front-face item(s). Critical gaps must be addressed to unlock automated scouting."
            )

        readiness = ReadinessScore(
            tenant_id=tenant_id,
            overall_score=final_score,
            ats_parse_score=ats_score,
            metric_coverage_score=metric_score,
            honest_keyword_score=kw_score,
            linkedin_headline_about_score=linkedin_score,
            experience_mirroring_score=exp_score,
            critical_todos_cleared_score=criticals_score,
            is_capped_at_69=is_capped,
            cap_reason=cap_reason,
        )
        session.add(readiness)

        # 7. Check if Readiness Gate Passed
        if final_score >= 70 and open_criticals == 0:
            await outbox.record_event(
                session=session,
                tenant_id=tenant_id,
                event_name="readiness.passed",
                payload={"score": final_score, "open_criticals": 0},
            )

        # Emit gaps.computed event
        await outbox.record_event(
            session=session,
            tenant_id=tenant_id,
            event_name="gaps.computed",
            payload={
                "score": final_score,
                "open_criticals": open_criticals,
                "is_capped": is_capped,
            },
        )
        await session.flush()
        return gap_report, todo_items, readiness

    @staticmethod
    async def resolve_todo(
        session: AsyncSession,
        tenant_id: str,
        todo_id: str,
        action: str,  # "accept", "edit", "dismiss"
        edited_text: Optional[str] = None,
        dismiss_reason: Optional[str] = None,
    ) -> Tuple[TodoItem, ReadinessScore]:
        """Resolves a to-do item and triggers dynamic Front-Face score recomputation (GE-05)."""
        todo_q = select(TodoItem).where(TodoItem.id == todo_id, TodoItem.tenant_id == tenant_id)
        todo = (await session.execute(todo_q)).scalar_one_or_none()

        if not todo:
            raise GapEngineError(f"TodoItem '{todo_id}' not found.")

        now = datetime.now(timezone.utc)
        clean_action = action.lower().strip()

        if clean_action == "dismiss":
            if not dismiss_reason or len(dismiss_reason.strip()) < 5:
                raise GapEngineError("Dismissing an item requires an explicit reason (logged).")
            todo.status = "dismissed"
            todo.dismiss_reason = dismiss_reason.strip()
            todo.resolved_at = now
        elif clean_action == "edit":
            if not edited_text:
                raise GapEngineError("Edited text cannot be empty.")
            todo.fix_draft = edited_text.strip()
            todo.status = "accepted"
            todo.resolved_at = now
        elif clean_action == "accept":
            todo.status = "accepted"
            todo.resolved_at = now
        else:
            raise GapEngineError(f"Invalid action '{action}'. Must be accept, edit, or dismiss.")

        await session.flush()

        # Emit todo.completed event
        await outbox.record_event(
            session=session,
            tenant_id=tenant_id,
            event_name="todo.completed",
            payload={"todo_id": todo.id, "action": clean_action, "severity": todo.severity},
        )

        # Dynamically recompute gaps and score (GE-05)
        _, _, updated_score = await GapEngine.compute_gaps(session, tenant_id)
        return todo, updated_score


gap_engine = GapEngine()
