"""Structured candidate facts the counsellor collects one question at a time.

These are the facts job matching and applications need but a resume rarely states:
experience, work mode, locations, sponsorship, salary floor, notice, deal-breakers.
Stored as one ProfileSection (step "facts").
"""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import ProfileSection

FACT_QUESTIONS: List[Dict[str, Any]] = [
    {"id": "years_experience", "kind": "number",
     "prompt": "How many years of professional experience do you have?"},
    {"id": "seniority", "kind": "choice", "prompt": "Which level are you aiming for next?",
     "options": [{"value": v, "label": v} for v in ("Junior", "Mid-level", "Senior", "Staff / Principal", "Manager / Lead")]},
    {"id": "work_mode", "kind": "choice", "prompt": "How do you want to work?",
     "options": [{"value": "remote_only", "label": "Remote only"}, {"value": "hybrid", "label": "Hybrid is fine"},
                 {"value": "onsite", "label": "Onsite is fine"}, {"value": "any", "label": "Anything works"}]},
    {"id": "locations", "kind": "list",
     "prompt": "Which cities or countries should I search? (comma-separated)"},
    {"id": "needs_sponsorship", "kind": "bool",
     "prompt": "Will you need visa sponsorship to work there?"},
    {"id": "salary_currency", "kind": "choice", "prompt": "Which currency are you paid in?",
     "options": [{"value": c, "label": c} for c in ("USD", "EUR", "GBP", "INR", "CAD", "AUD", "SGD")]},
    {"id": "salary_min", "kind": "number",
     "prompt": "What's the lowest yearly base salary you'd accept?"},
    {"id": "notice_weeks", "kind": "number",
     "prompt": "How many weeks' notice do you need before starting?"},
    {"id": "deal_breakers", "kind": "list",
     "prompt": "Anything that's a hard no? (e.g. on-call, crypto, 5 days in office)"},
    {"id": "blacklist_companies", "kind": "list",
     "prompt": "Any companies you don't want to apply to?"},
    {"id": "target_companies", "kind": "list",
     "prompt": "Any companies you'd love to work at? I'll watch their job boards too."},
]
_BY_ID = {q["id"]: q for q in FACT_QUESTIONS}
_INTERNAL_LISTS = {"declined_skills", "skipped"}  # set by the product, not asked
_INTERNAL_DICTS = {
    "company_boards",  # company -> "portal:slug" or None (scout discovery cache)
    "apply_profile",   # contact details used to fill application forms
    "apply_answers",   # normalized question text -> the candidate's answer, reused across forms
}


def _clean_list(value: Any, key: str) -> List[str]:
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    out: List[str] = []
    for item in value:
        item = str(item).strip()
        if item and item.lower() not in {o.lower() for o in out}:
            out.append(item)
    return out


def _validate(key: str, value: Any) -> Any:
    if key in _INTERNAL_LISTS:
        return _clean_list(value, key)
    if key in _INTERNAL_DICTS:
        if not isinstance(value, dict):
            raise ValueError(f"{key} must be an object")
        if key == "company_boards":
            return {str(k): (str(v) if v else None) for k, v in value.items()}
        return {str(k): v for k, v in value.items() if isinstance(v, (str, list)) and v not in ("", [])}
    q = _BY_ID.get(key)
    if q is None:
        raise ValueError(f"Unknown fact '{key}'")
    kind = q["kind"]
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 10_000_000:
            raise ValueError(f"{key} must be a non-negative number")
        return int(value) if float(value).is_integer() else value
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false")
        return value
    if kind == "choice":
        if value not in {o["value"] for o in q["options"]}:
            raise ValueError(f"{key} must be one of the offered options")
        return value
    if kind == "list":
        return _clean_list(value, key)
    return str(value).strip()


async def _row(session: AsyncSession, tenant_id: str) -> Optional[ProfileSection]:
    return (await session.execute(
        select(ProfileSection).where(ProfileSection.tenant_id == tenant_id, ProfileSection.step == "facts")
    )).scalar_one_or_none()


async def get_facts(session: AsyncSession, tenant_id: str) -> Dict[str, Any]:
    row = await _row(session, tenant_id)
    return dict(row.body) if row else {}


async def update_facts(session: AsyncSession, tenant_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = {key: _validate(key, value) for key, value in patch.items()}
    row = await _row(session, tenant_id)
    if row is None:
        row = ProfileSection(tenant_id=tenant_id, section="facts", step="facts", body={}, input_mode="text")
        session.add(row)
    row.body = {**(row.body or {}), **cleaned}  # reassign so the JSON change is persisted
    await session.flush()
    return dict(row.body)


def next_question(facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    skipped = set(facts.get("skipped") or [])
    return next((q for q in FACT_QUESTIONS if q["id"] not in facts and q["id"] not in skipped), None)


def completeness(facts: Dict[str, Any]) -> Tuple[int, int]:
    return sum(1 for q in FACT_QUESTIONS if q["id"] in facts), len(FACT_QUESTIONS)
