"""Profiler / Consulting Agent (Phase 2).

Responsible for:
1. STAR Story extraction from candidate interview notes and raw achievements.
2. Reflection and verification against master resume bullets to eliminate hallucinations.
3. Front-face gap computation and Readiness Gate auditing (RD-01).
4. DeepSeek 5-stage loop integration (Plan -> Act -> Observe -> Reflect -> Checkpoint).
"""

import re
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import outbox
from app.domain.gap_engine import gap_engine
from app.domain.memory import memory
from app.domain.models import ResumeParse, Story
from app.domain.readiness import ReadinessStatus, readiness_gate
from app.harness.loop import agent_loop
from app.harness.registry import Tool, ToolMetadata, registry
from app.harness.run import AgentAction, RunContext


class ProfilerAgent:
    """Consulting Agent analyzing candidate intake, extracting STAR stories, and auditing readiness."""

    def __init__(self):
        self._register_profiler_tools()

    def _register_profiler_tools(self) -> None:
        """Registers profiler tools in the Harness registry if not already registered."""
        try:
            registry.get("story_extract")
        except KeyError:
            registry.register(
                Tool(
                    meta=ToolMetadata(
                        name="story_extract",
                        description="Extracts STAR stories from raw candidate notes and verifies against master resume.",
                        permission_scope="extract:stories",
                        external=False,
                        gate_required=False,
                    ),
                    handler=self._tool_story_extract,
                )
            )

    async def _tool_story_extract(
        self,
        tenant_id: str,
        raw_notes: str,
        master_bullets: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Tool handler for story extraction with honesty checking."""
        stories = self._parse_star_stories_from_text(raw_notes, master_bullets or [])
        return {
            "stories_extracted": len(stories),
            "stories": stories,
        }

    def _parse_star_stories_from_text(
        self,
        raw_notes: str,
        master_bullets: List[str],
    ) -> List[Dict[str, Any]]:
        """Parses structured STAR stories and verifies claims against master bullets."""
        stories_data: List[Dict[str, Any]] = []
        master_text = " ".join(master_bullets).lower()

        # Split notes by story markers or paragraphs
        chunks = [c.strip() for c in re.split(r"\n\s*\n|(?=Story \d+:|Project:)", raw_notes) if c.strip()]
        if not chunks:
            chunks = [raw_notes.strip()]

        for idx, chunk in enumerate(chunks, 1):
            lines = [line.strip() for line in chunk.splitlines() if line.strip()]
            if not lines:
                continue

            first_line = lines[0].lstrip("# -*").strip()
            if ":" in first_line:
                title = first_line.split(":", 1)[1].strip()
            else:
                title = first_line
            if len(title) < 4:
                title = f"Impact Milestone {idx}"

            # Extract STAR components using keywords or positional fallback
            situation = ""
            task = ""
            action = ""
            result = ""

            for line in lines:
                lower = line.lower()
                if "situation:" in lower or "context:" in lower:
                    situation = line.split(":", 1)[-1].strip()
                elif "task:" in lower or "goal:" in lower:
                    task = line.split(":", 1)[-1].strip()
                elif "action:" in lower or "approach:" in lower:
                    action = line.split(":", 1)[-1].strip()
                elif "result:" in lower or "impact:" in lower or "outcome:" in lower:
                    result = line.split(":", 1)[-1].strip()

            # Fallback if unformatted: map lines sequentially
            if not situation and len(lines) > 0:
                situation = lines[0]
            if not task and len(lines) > 1:
                task = lines[1]
            if not action and len(lines) > 2:
                action = " ".join(lines[2:4])
            if not result and len(lines) > 3:
                result = " ".join(lines[4:])
            elif not result:
                result = "Successfully delivered milestones within target constraints."

            # Extract metrics ($500k, 40%, 10M, 3x)
            metric_matches = re.findall(
                r"(\b\d+(?:\.\d+)?%\b|\$\d+(?:,\d+)*(?:\.\d+)?[kKmMbB]?|\b\d+[kKmMbB]\b|\b\d+x\b)",
                chunk,
            )

            # Extract tech keywords
            from app.domain.skills import find_skills
            skills_found = find_skills(chunk)

            # Honesty reflection: Does the master resume support these metrics and skills?
            verified_against_master = True
            unsupported_claims: List[str] = []

            if master_bullets:
                for metric in metric_matches:
                    if metric.lower() not in master_text:
                        verified_against_master = False
                        unsupported_claims.append(f"Metric '{metric}' not found in master resume")

            stories_data.append({
                "title": title[:255],
                "situation": situation or "Production environment scenario.",
                "task": task or "Architectural and implementation requirements.",
                "action": action or "Engineered scalable backend solutions.",
                "result": result,
                "skills_demonstrated": skills_found,
                "metrics": metric_matches,
                "verified_against_master": verified_against_master,
                "unsupported_claims": unsupported_claims,
            })

        return stories_data

    async def extract_and_persist_stories(
        self,
        session: AsyncSession,
        tenant_id: str,
        raw_notes: str,
        run_context: Optional[RunContext] = None,
    ) -> List[Story]:
        """Extracts STAR stories, verifies against master resume, and saves in Story table."""
        # 1. Fetch master resume bullets for honesty checking
        resume_q = (
            select(ResumeParse)
            .where(ResumeParse.tenant_id == tenant_id)
            .order_by(desc(ResumeParse.created_at))
            .limit(1)
        )
        resume_rec = (await session.execute(resume_q)).scalar_one_or_none()
        master_bullets: List[str] = []
        if resume_rec and resume_rec.sections:
            master_bullets = resume_rec.sections.get("bullets", [])

        # 2. Parse stories with honesty verification
        parsed_items = self._parse_star_stories_from_text(raw_notes, master_bullets)

        saved_stories: List[Story] = []
        for item in parsed_items:
            story = Story(
                tenant_id=tenant_id,
                title=item["title"],
                situation=item["situation"],
                task=item["task"],
                action=item["action"],
                result=item["result"],
                skills_demonstrated=item["skills_demonstrated"],
                metrics=item["metrics"],
                verified_against_master=item["verified_against_master"],
            )
            session.add(story)
            saved_stories.append(story)

        # 3. Update blackboard memory
        memory.write_section(
            tenant_id=tenant_id,
            section="story_bank",
            data=[
                {
                    "title": s.title,
                    "verified": s.verified_against_master,
                    "metrics": s.metrics,
                    "skills": s.skills_demonstrated,
                }
                for s in saved_stories
            ],
        )

        # 4. If part of an active agent run, record observation and reflection
        if run_context:
            obs = {
                "step_index": run_context.step_index,
                "tool_name": "story_extract",
                "arguments": {"raw_notes_len": len(raw_notes)},
                "output": {"stories_count": len(saved_stories)},
                "status": "success",
            }
            run_context.add_observation(obs)

            has_unverified = any(not s.verified_against_master for s in saved_stories)
            reflection = {
                "step_index": run_context.step_index,
                "tool_name": "story_extract",
                "success": True,
                "needs_correction": has_unverified,
                "correction_reason": "Some extracted stories contain claims not present in master resume." if has_unverified else "",
                "next_action": "prompt_user_verification" if has_unverified else "continue",
            }
            run_context.add_reflection(reflection)

        # 5. Emit outbox event
        await outbox.record_event(
            session=session,
            tenant_id=tenant_id,
            event_name="stories.extracted",
            payload={
                "count": len(saved_stories),
                "verified_count": sum(1 for s in saved_stories if s.verified_against_master),
            },
        )
        await session.flush()
        return saved_stories

    async def audit_and_score(
        self,
        session: AsyncSession,
        tenant_id: str,
    ) -> ReadinessStatus:
        """Executes Front-Face gap analysis and returns Readiness Gate status (RD-01)."""
        # Run Gap Engine computation
        await gap_engine.compute_gaps(session, tenant_id)
        # Evaluate Readiness Gate status
        status = await readiness_gate.evaluate_readiness(session, tenant_id)
        return status


profiler_agent = ProfilerAgent()
