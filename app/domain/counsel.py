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


def _format_history(sections: Dict[str, ProfileSection]) -> List[Dict[str, Any]]:
    history = []
    for s in COUNSEL_STEPS:
        if s in sections:
            sec = sections[s]
            ans_text = ""
            if s == "linkedin":
                ans_text = sec.body.get("raw") or sec.body.get("url_or_text", "")
            elif s == "resume":
                ans_text = sec.body.get("raw") or sec.body.get("resume_id_or_text", "Resume PDF Uploaded")
            elif s == "target_work":
                ans_text = sec.body.get("background", "")
            elif s == "priority_role":
                prio_id = sec.body.get("priority_role_id", "")
                role_def = roles_service.find_role_in_catalog(prio_id)
                ans_text = role_def["title"] if role_def else prio_id
            elif s == "management":
                ans_text = (
                    "Yes, I have management experience"
                    if sec.body.get("management")
                    else "No management experience"
                )
            elif s == "location":
                ans_text = sec.body.get("location", "")
            elif s == "authorization":
                ans_text = sec.body.get("authorization", "")
            elif s == "preferences":
                more = sec.body.get("more_of", "")
                avoid = sec.body.get("avoid", "")
                ans_text = f"More of: {more}" + (f" | Avoid: {avoid}" if avoid else "")

            history.append({
                "step": s,
                "prompt": PROMPTS[s],
                "answer": ans_text,
                "input_mode": sec.input_mode or "text",
            })
    return history


async def get_counsel_state(session: AsyncSession, tenant_id: str) -> Dict[str, Any]:
    """Returns the current step, prompt, choices, and previous history for the candidate."""
    stmt = (
        select(ProfileSection)
        .where(ProfileSection.tenant_id == tenant_id)
        .order_by(ProfileSection.created_at.asc())
    )
    res = await session.execute(stmt)
    sections = {row.step: row for row in res.scalars().all()}
    history = _format_history(sections)

    for step in COUNSEL_STEPS:
        if step not in sections:
            choices: List[Any] = []
            if step == "priority_role" and "target_work" in sections:
                choices = sections["target_work"].body.get("suggestions", [])
            return {
                "step": step,
                "prompt": PROMPTS[step],
                "choices": choices,
                "history": history,
                "done": False,
            }

    return {
        "step": None,
        "prompt": "All onboarding questions answered.",
        "choices": [],
        "history": history,
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
    # 1. Verify step
    if step == "target_roles":
        step = "target_work"

    if step not in COUNSEL_STEPS:
        raise CounselValidationError(f"Unknown step '{step}'.")

    stmt = select(ProfileSection).where(ProfileSection.tenant_id == tenant_id)
    res = await session.execute(stmt)
    existing_by_step = {row.step: row for row in res.scalars().all()}

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
        mgmt_sec = existing_by_step.get("management")
        has_mgmt = mgmt_sec.body.get("management", False) if mgmt_sec else False
        max_allowed = 4 if has_mgmt else 3

        if suggestions and text not in suggestions:
            # If not in suggestions, accept or fall back to suggestion list, capped at max_allowed
            role_ids = list(dict.fromkeys([text] + suggestions))[:max_allowed]
        else:
            role_ids = (suggestions or [text])[:max_allowed]

        await roles_service.select_roles(
            session=session,
            tenant_id=tenant_id,
            role_ids=role_ids,
            mgmt_experience=has_mgmt,
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

    # 3. Store or update section (upsert)
    existing_row = (
        await session.execute(
            select(ProfileSection).where(
                ProfileSection.tenant_id == tenant_id,
                ProfileSection.step == step,
            )
        )
    ).scalar_one_or_none()

    if existing_row:
        existing_row.section = section_key
        existing_row.body = body
        existing_row.input_mode = input_mode
        section_row = existing_row
    else:
        section_row = ProfileSection(
            tenant_id=tenant_id,
            section=section_key,
            step=step,
            body=body,
            input_mode=input_mode,
        )
        session.add(section_row)
    await session.flush()

    # Update memory of existing steps for history calculation
    existing_by_step[step] = section_row
    history = _format_history(existing_by_step)

    # If preferences is saved, unlock todos stage
    if step == "preferences":
        await set_stage(session, tenant_id, "todos")

    # 4. Return next step state (first unanswered step or completed)
    next_unanswered = None
    for s in COUNSEL_STEPS:
        if s not in existing_by_step:
            next_unanswered = s
            break

    if next_unanswered is not None:
        next_choices: List[Any] = []
        if next_unanswered == "priority_role" and "target_work" in existing_by_step:
            next_choices = existing_by_step["target_work"].body.get("suggestions", [])
        return {
            "step": next_unanswered,
            "prompt": PROMPTS[next_unanswered],
            "choices": next_choices,
            "history": history,
            "done": False,
        }

    return {
        "step": None,
        "prompt": "All onboarding questions answered.",
        "choices": [],
        "history": history,
        "done": True,
    }
