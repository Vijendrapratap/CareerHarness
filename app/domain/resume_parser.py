"""Resume Intake & Honest Skill Extraction Service (F3, AT-06, ON-03)."""

import re
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import outbox
from app.domain.memory import memory
from app.domain.models import ResumeParse

# Regex to detect impact metrics ($500k, 40%, 10M, 3x)
METRIC_REGEX = re.compile(
    r"(\b\d+(?:\.\d+)?%\b|\$\d+(?:,\d+)*(?:\.\d+)?[kKmMbB]?|\b\d+[kKmMbB]\b|\b\d+x\b)"
)

# Common technical and domain skills dictionary for extraction
KNOWN_SKILLS = [
    "Python", "JavaScript", "TypeScript", "React", "Next.js", "Node.js", "SQL",
    "PostgreSQL", "Redis", "Docker", "Kubernetes", "AWS", "GCP", "GraphQL",
    "REST APIs", "Microservices", "Distributed Systems", "FastAPI", "Celery",
    "Git", "CI/CD", "Tailwind CSS", "Linux", "TDD", "System Design",
]


class ResumeParserService:
    """Parses candidate resume text into structured sections with honest skill tagging."""

    @staticmethod
    def extract_metrics(text: str) -> List[Dict[str, Any]]:
        """Identifies measurable impact metrics in bullets."""
        found = []
        for match in METRIC_REGEX.finditer(text):
            found.append({
                "metric": match.group(0),
                "position": match.start(),
            })
        return found

    @staticmethod
    def extract_skills_unverified(text: str) -> List[Dict[str, Any]]:
        """Extracts skills from text with verified=False by default (AT-06).

        Guarantees:
        - Parsed skills are NEVER auto-marked verified.
        - Honesty tagging is strictly enforced.
        """
        extracted = []
        lowered_text = text.lower()
        for skill in KNOWN_SKILLS:
            pattern = rf"\b{re.escape(skill.lower())}\b"
            if re.search(pattern, lowered_text):
                extracted.append({
                    "name": skill,
                    "verified": False,  # AT-06: Strict unverified default
                    "source": "resume_parse",
                })
        return extracted

    @staticmethod
    async def parse_resume_text(
        session: AsyncSession,
        tenant_id: str,
        filename: str,
        content: str,
    ) -> ResumeParse:
        """Parses resume text into sections, metrics, and unverified skills."""
        cleaned_text = content.strip()

        # ON-03: Scanned PDF / degraded text detection
        confidence_score = 1.0
        if len(cleaned_text) < 50:
            # Low character count indicates scanned image or empty file
            confidence_score = 0.3

        # Parse sections (basic heuristics)
        lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
        bullets = [line for line in lines if line.startswith(("-", "•", "*", "–")) or len(line) > 30]

        extracted_skills = ResumeParserService.extract_skills_unverified(cleaned_text)
        metrics = ResumeParserService.extract_metrics(cleaned_text)

        sections = {
            "summary": lines[0] if lines else "",
            "bullets": bullets,
            "line_count": len(lines),
        }

        resume_parse = ResumeParse(
            tenant_id=tenant_id,
            filename=filename,
            raw_text=cleaned_text,
            sections=sections,
            extracted_skills=extracted_skills,
            metrics=metrics,
            confidence_score=confidence_score,
        )
        session.add(resume_parse)

        # Update blackboard memory with parsed bullets
        memory.write_section(
            tenant_id=tenant_id,
            section="resume_bullets",
            data=[{"text": b, "verified": True} for b in bullets],
        )

        # Emit resume.parsed event
        await outbox.record_event(
            session=session,
            tenant_id=tenant_id,
            event_name="resume.parsed",
            payload={
                "filename": filename,
                "skills_found": len(extracted_skills),
                "metrics_found": len(metrics),
                "confidence_score": confidence_score,
            },
        )
        await session.flush()
        return resume_parse

    @staticmethod
    async def confirm_skill(
        session: AsyncSession,
        tenant_id: str,
        parse_id: str,
        skill_name: str,
    ) -> ResumeParse:
        """User confirms a parsed skill, elevating it to verified status (AT-06)."""
        query = select(ResumeParse).where(
            ResumeParse.id == parse_id,
            ResumeParse.tenant_id == tenant_id,
        )
        record = (await session.execute(query)).scalar_one_or_none()
        if not record:
            raise ValueError(f"Resume parse record '{parse_id}' not found.")

        updated_skills = []
        for s in record.extracted_skills:
            if s["name"].lower() == skill_name.lower():
                updated_skills.append({**s, "verified": True})
            else:
                updated_skills.append(s)

        record.extracted_skills = updated_skills
        await session.flush()

        # Update verified skills in blackboard memory
        verified_names = [s["name"] for s in updated_skills if s.get("verified")]
        memory.write_section(tenant_id=tenant_id, section="verified_skills", data=verified_names)

        return record


resume_parser = ResumeParserService()
