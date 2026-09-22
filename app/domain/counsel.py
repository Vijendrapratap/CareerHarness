"""Candidate Counsellor Domain Service (Task 4).

Interviews the candidate through 8 structured steps and writes profile sections.
"""

import re
from typing import Any, Dict, List, Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.journey import get_or_create_journey, set_stage
from app.domain.models import ProfileSection
from app.domain.roles import roles_service

COUNSEL_STEPS = (
    "linkedin",
    "resume",
    "target_work",
    "priority_role",
    "management",
    "location",
    "authorization",
    "preferences",
)

PROMPTS = {
    "linkedin": "Paste your LinkedIn URL or the About and Experience text.",
    "resume": "Upload your resume PDF.",
    "target_work": "What kind of work do you want next?",
    "priority_role": "Which of these is the priority role?",
    "management": "Have you managed people or a program?",
    "location": "Where do you want to work, and is remote acceptable?",
    "authorization": "Are you authorized to work in the country you are targeting, and do you need sponsorship?",
    "preferences": "What do you want more of, and what do you want to avoid?",
}

STEP_SECTION_MAP = {
    "linkedin": "linkedin",
    "resume": "resume",
    "target_work": "target_roles",
    "priority_role": "target_roles",
    "management": "preferences",
    "location": "preferences",
    "authorization": "preferences",
    "preferences": "preferences",
}


class CounselOrderError(Exception):
    """Raised when an answer is provided out of order."""
    pass


class CounselValidationError(Exception):
    """Raised when an answer fails step validation."""
    pass


async def get_counsel_state(session: AsyncSession, tenant_id: str) -> Dict[str, Any]:
    """Returns the current step, prompt, and choices for the next unanswered step."""
    stmt = (
        select(ProfileSection)
        .where(ProfileSection.tenant_id == tenant_id)
        .order_by(ProfileSection.created_at.asc())
    )
    res = await session.execute(stmt)
    sections = {row.step: row for row in res.scalars().all()}

    for step in COUNSEL_STEPS:
        if step not in sections:
            choices: List[Any] = []
            if step == "priority_role" and "target_work" in sections:
                choices = sections["target_work"].body.get("suggestions", [])
            return {
                "step": step,
                "prompt": PROMPTS[step],
                "choices": choices,
                "done": False,
            }

    return {
        "step": None,
        "prompt": "All onboarding questions answered.",
        "choices": [],
        "done": True,
    }


async def record_answer(
    session: AsyncSession,
    tenant_id: str,
    step: str,
    text: str,
    input_mode: Literal["text", "mic"] = "text",
) -> Dict[str, Any]:
    """Records the candidate's answer for the expected step and updates journey state."""
    # 1. Verify step order
    stmt = select(ProfileSection).where(ProfileSection.tenant_id == tenant_id)
    res = await session.execute(stmt)
    existing_by_step = {row.step: row for row in res.scalars().all()}

    expected_step = None
    for s in COUNSEL_STEPS:
        if s not in existing_by_step:
            expected_step = s
            break

    if expected_step is None:
        return {
            "step": None,
            "prompt": "All onboarding questions answered.",
            "choices": [],
            "done": True,
        }

    if step != expected_step:
        raise CounselOrderError(f"Expected step '{expected_step}', but got '{step}'.")

    section_key = STEP_SECTION_MAP[step]
    body: Dict[str, Any] = {}

    # 2. Process step-specific logic
    if step == "linkedin":
        body = {"raw": text, "url_or_text": text}

    elif step == "resume":
        body = {"raw": text, "resume_id_or_text": text}

    elif step == "target_work":
        suggestions = [r["id"] for r in roles_service.suggest_roles(text, mgmt_experience=False)]
        body = {"background": text, "suggestions": suggestions}

    elif step == "priority_role":
        target_work_sec = existing_by_step.get("target_work")
        suggestions = target_work_sec.body.get("suggestions", []) if target_work_sec else []
        if suggestions and text not in suggestions:
            # If not in suggestions, accept or fall back to suggestion list
            role_ids = list(dict.fromkeys([text] + suggestions))
        else:
            role_ids = suggestions or [text]

        await roles_service.select_roles(
            session=session,
            tenant_id=tenant_id,
            role_ids=role_ids,
            mgmt_experience=False,
            priority_role_id=text,
        )
        body = {
            "background": target_work_sec.body.get("background", "") if target_work_sec else "",
            "suggestions": suggestions,
            "priority_role_id": text,
        }

    elif step == "management":
        cleaned = text.strip().lower()
        if cleaned not in ("yes", "no"):
            raise CounselValidationError("Answer must be 'yes' or 'no'.")
        is_mgmt = cleaned == "yes"

        if is_mgmt and "target_work" in existing_by_step:
            bg = existing_by_step["target_work"].body.get("background", "")
            updated_roles = roles_service.suggest_roles(bg, mgmt_experience=True)
            new_role_ids = [r["id"] for r in updated_roles]
            prio = existing_by_step.get("priority_role")
            prio_id = prio.body.get("priority_role_id") if prio else None
            await roles_service.select_roles(
                session=session,
                tenant_id=tenant_id,
                role_ids=new_role_ids,
                mgmt_experience=True,
                priority_role_id=prio_id,
            )
        body = {"management": is_mgmt}

    elif step == "location":
        body = {"location": text.strip()}

    elif step == "authorization":
        body = {"authorization": text.strip()}

    elif step == "preferences":
        # Split on "avoid" if present
        if re.search(r"\bavoid\b", text, flags=re.IGNORECASE):
            parts = re.split(r"\bavoid\b", text, maxsplit=1, flags=re.IGNORECASE)
            more_of = parts[0].strip(" .,-")
            avoid = parts[1].strip(" .,-")
        else:
            more_of = text.strip()
            avoid = ""
        body = {"more_of": more_of, "avoid": avoid}

    # 3. Store or update section
    section_row = ProfileSection(
        tenant_id=tenant_id,
        section=section_key,
        step=step,
        body=body,
        input_mode=input_mode,
    )
    session.add(section_row)
    await session.flush()

    # If preferences is saved, unlock todos stage
    if step == "preferences":
        await set_stage(session, tenant_id, "todos")

    # 4. Return next step state
    curr_idx = COUNSEL_STEPS.index(step)
    if curr_idx + 1 < len(COUNSEL_STEPS):
        next_step = COUNSEL_STEPS[curr_idx + 1]
        next_choices: List[Any] = []
        if next_step == "priority_role":
            next_choices = body.get("suggestions", [])
        return {
            "step": next_step,
            "prompt": PROMPTS[next_step],
            "choices": next_choices,
            "done": False,
        }

    return {
        "step": None,
        "prompt": "All onboarding questions answered.",
        "choices": [],
        "done": True,
    }
