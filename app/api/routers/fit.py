"""Candidate facts (asked one at a time by the counsellor) and the profile fix loop."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.candidate_facts import completeness, get_facts, next_question, update_facts
from app.domain.fit_service import apply_ready_count, evaluate_tenant, fix_impact
from app.domain.resume_parser import verify_skill

router = APIRouter(tags=["Fit & Profile Facts"])


def _facts_payload(facts: Dict[str, Any]) -> Dict[str, Any]:
    answered, total = completeness(facts)
    return {"facts": facts, "next_question": next_question(facts), "answered": answered, "total": total}


@router.get("/api/profile/facts")
async def read_facts(tenant_id: str = Depends(get_tenant_id), session: AsyncSession = Depends(get_db)):
    return _facts_payload(await get_facts(session, tenant_id))


@router.patch("/api/profile/facts")
async def patch_facts(
    patch: Dict[str, Any],
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        facts = await update_facts(session, tenant_id, patch)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await evaluate_tenant(session, tenant_id)  # gates and logistics depend on facts
    return _facts_payload(facts)


class SkillRequest(BaseModel):
    skill: str


@router.get("/api/fit/fixes")
async def list_fixes(tenant_id: str = Depends(get_tenant_id), session: AsyncSession = Depends(get_db)):
    """Skill confirmations ranked by how many jobs each would lift over the apply line."""
    return await fix_impact(session, tenant_id)


@router.post("/api/fit/fixes/confirm-skill")
async def confirm_skill(
    req: SkillRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """The candidate states they have this skill; it becomes verified and every job is rescored."""
    before = await apply_ready_count(session, tenant_id)
    if not await verify_skill(session, tenant_id, req.skill.strip()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload your resume first.")
    await evaluate_tenant(session, tenant_id)
    after = await apply_ready_count(session, tenant_id)
    return {"skill": req.skill, "unlocked": after - before, "apply_ready": after}


class SkillsRequest(BaseModel):
    skills: List[str]


@router.post("/api/fit/fixes/confirm-skills")
async def confirm_skills(
    req: SkillsRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Batch version for the resume checklist: confirm several skills, rescore once."""
    before = await apply_ready_count(session, tenant_id)
    for skill in {s.strip() for s in req.skills if s.strip()}:
        if not await verify_skill(session, tenant_id, skill):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload your resume first.")
    await evaluate_tenant(session, tenant_id)
    after = await apply_ready_count(session, tenant_id)
    return {"skills": req.skills, "unlocked": after - before, "apply_ready": after}


@router.post("/api/fit/fixes/decline-skill")
async def decline_skill(
    req: SkillRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """The candidate honestly doesn't have this skill: stop suggesting it; it stays a real gap."""
    declined = (await get_facts(session, tenant_id)).get("declined_skills") or []
    await update_facts(session, tenant_id, {"declined_skills": [*declined, req.skill.strip()]})
    await evaluate_tenant(session, tenant_id)
    return {"skill": req.skill, "apply_ready": await apply_ready_count(session, tenant_id)}
