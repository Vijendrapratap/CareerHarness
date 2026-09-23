"""Counsellor API Router (Task 4)."""

from typing import Any, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.core.config import settings
from app.domain.counsel import (
    CounselOrderError,
    CounselValidationError,
    get_counsel_state,
    record_answer,
)
from app.domain.roles import RoleSelectionError
from app.domain.scout import scan_in_background

router = APIRouter(prefix="/api/counsel", tags=["Candidate Counsellor"])


class CounselAnswerRequest(BaseModel):
    step: str
    text: str
    input_mode: Literal["text", "mic"] = "text"


class CounselHistoryItem(BaseModel):
    step: str
    prompt: str
    answer: str
    input_mode: str = "text"


class CounselStateResponse(BaseModel):
    step: Optional[str] = None
    prompt: str
    choices: List[Any] = []
    history: List[CounselHistoryItem] = []
    done: bool


@router.get("", response_model=CounselStateResponse)
async def get_counsel(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    return await get_counsel_state(db, tenant_id)


@router.post("/answer", response_model=CounselStateResponse)
async def submit_counsel_answer(
    request: CounselAnswerRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await record_answer(
            session=db,
            tenant_id=tenant_id,
            step=request.step,
            text=request.text,
            input_mode=request.input_mode,
        )
    except (CounselOrderError, RoleSelectionError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except CounselValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


class CounselChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class CounselChatRequest(BaseModel):
    message: str
    history: List[CounselChatMessage] = []
    context: Optional[dict] = None


class CounselChatResponse(BaseModel):
    reply: str
    detected_attributes: dict = {}
    stage: str = "counsel"


@router.post("/chat", response_model=CounselChatResponse)
async def chat_with_counsellor(
    request: CounselChatRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Live interactive chat with the AI Career Counsellor to build a strong candidate persona."""
    import httpx

    from app.core.keyvault import KeyVaultService
    from app.domain.journey import get_or_create_journey

    message = request.message.strip()
    history = request.history

    # Extract detected attributes from message
    detected: dict = {}
    lower_msg = message.lower()

    # Leadership / Management detection
    if any(term in lower_msg for term in ["manage", "lead a team", "lead team", "lead squads", "people lead", "engineering manager", "head of", "director"]):
        detected["management"] = True
    elif any(term in lower_msg for term in ["individual contributor", "ic role", "hands-on", "pure engineering", "senior engineer", "staff engineer"]):
        detected["management"] = False

    # Location / Work setup detection
    if "remote" in lower_msg:
        detected["location"] = "Remote (Flexible)"
    elif any(term in lower_msg for term in ["san francisco", "bay area", "silicon valley"]):
        detected["location"] = "Hybrid / On-site (San Francisco / Bay Area)"
    elif any(term in lower_msg for term in ["new york", "nyc"]):
        detected["location"] = "Hybrid / On-site (New York City)"
    elif any(term in lower_msg for term in ["london", "uk", "europe"]):
        detected["location"] = "Hybrid / Remote (London / UK / Europe)"
    elif any(term in lower_msg for term in ["bengaluru", "bangalore", "india"]):
        detected["location"] = "Hybrid / Remote (Bengaluru / India)"

    # Work Authorization detection
    if any(term in lower_msg for term in ["citizen", "permanent resident", "green card", "no sponsorship", "authorized"]):
        detected["authorization"] = "Authorized (No sponsorship required)"
    elif any(term in lower_msg for term in ["visa", "sponsorship", "h1b", "h-1b", "require sponsorship"]):
        detected["authorization"] = "Requires Visa Sponsorship"
    elif any(term in lower_msg for term in ["contract", "c2c", "b2b"]):
        detected["authorization"] = "Open to Contractor / B2B"

    # Dealbreakers / Preferences detection
    if any(term in lower_msg for term in ["avoid", "dealbreaker", "hate", "don't want", "toxic", "on-call", "monolith"]):
        detected["preferences"] = message

    # Try calling OpenRouter with DeepSeek Flash / Chat
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        try:
            api_key = await KeyVaultService.get_decrypted_key(db, tenant_id, "openrouter")
        except Exception:
            api_key = None

    # What the counsellor knows, from the database rather than the browser.
    from app.domain.candidate_facts import get_facts, next_question
    from app.domain.fit_service import apply_ready_count, candidate_snapshot, fix_impact

    snap = await candidate_snapshot(db, tenant_id)
    missing = next_question(await get_facts(db, tenant_id))
    top_fixes = (await fix_impact(db, tenant_id))[:3]
    ready = await apply_ready_count(db, tenant_id)
    known_facts = {k: v for k, v in snap.facts.items() if k not in ("skipped", "declined_skills")}
    fix_lines = "\n".join(
        f"- {f['skill']}: confirming it would unlock {f['jobs_unlocked']} job(s), improve {f['jobs_improved']}"
        + (" (already in their resume, just unconfirmed)" if f["in_resume"] else " (not in their resume)")
        for f in top_fixes
    ) or "- none right now"

    reply = ""
    if api_key and not api_key.startswith("sk-test-"):
        try:
            system_prompt = (
                "You are the CareerHarness career counsellor. You help the candidate find better jobs faster by "
                "getting their profile honest and complete, then pointing them at the highest-leverage fixes.\n\n"
                f"Target roles: {', '.join(snap.role_titles) or 'not chosen yet'}\n"
                f"Confirmed skills: {', '.join(sorted(snap.verified_skills)) or 'none yet'}\n"
                f"In resume but unconfirmed: {', '.join(sorted(snap.resume_skills)) or 'none'}\n"
                f"Known facts: {known_facts or 'none yet'}\n"
                f"Jobs currently at or above the 4.0/5 apply line: {ready}\n"
                f"Biggest fixes (skills to confirm):\n{fix_lines}\n"
                f"Next missing fact to collect: {missing['prompt'] if missing else 'none, all facts collected'}\n\n"
                "Rules:\n"
                "- Answer the candidate's question first, concretely, in 1-2 short paragraphs of plain text (no markdown).\n"
                "- Then either ask the ONE next missing fact above, or suggest the single biggest fix and why it matters.\n"
                "- Never tell them to claim a skill they haven't used. A skill they lack stays an honest gap; "
                "suggest how to close it (a small project, a course) instead.\n"
                "- Jobs below the apply line can't be applied to; say so plainly when relevant."
            )

            messages_payload = [{"role": "system", "content": system_prompt}]
            for m in history[-6:]:  # keep last 6 turns for context
                messages_payload.append({"role": m.role, "content": m.content})
            messages_payload.append({"role": "user", "content": message})

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "deepseek/deepseek-v4.1-flash",
                        "messages": messages_payload,
                        "max_tokens": 350,  # 1-2 short paragraphs
                        "reasoning": {"enabled": False},  # thinking took 20-30s and ate the token budget
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    reply = data["choices"][0]["message"]["content"].strip()
        except Exception:
            reply = ""

    # Without a model: still useful — ask the next missing fact, or point at the biggest fix.
    if not reply:
        if missing:
            reply = f"Noted. To score jobs for you properly I need one more thing: {missing['prompt']}"
        elif top_fixes:
            f = top_fixes[0]
            gain = (
                f"it would lift {f['jobs_unlocked']} job(s) over the apply line"
                if f["jobs_unlocked"] else f"it would improve {f['jobs_improved']} of your matches"
            )
            reply = (
                f"Your biggest win right now is {f['skill']}: {gain}. If you've really used it, confirm it on the Jobs page. "
                "If not, it stays an honest gap, and I can suggest a small project to close it."
            )
        else:
            reply = f"Your profile is in good shape: {ready} job(s) are ready to apply. Ask me anything about them."

    journey = await get_or_create_journey(db, tenant_id)
    return CounselChatResponse(reply=reply, detected_attributes=detected, stage=journey.stage)


class PreferencesUpdateRequest(BaseModel):
    work_arrangement: Optional[str] = None
    location: Optional[str] = None
    authorization: Optional[str] = None
    management: Optional[bool] = None
    dealbreakers: Optional[List[str]] = None
    preferences: Optional[str] = None


@router.post("/preferences")
async def update_counsel_preferences(
    request: PreferencesUpdateRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Saves candidate preferences directly into profile sections without requiring back-and-forth chat."""
    from sqlalchemy import select

    from app.domain.models import ProfileSection

    updates: dict = {}
    loc_parts = []
    if request.work_arrangement:
        loc_parts.append(request.work_arrangement)
    if request.location:
        loc_parts.append(request.location)
    if loc_parts:
        updates["location"] = {"location": " • ".join(loc_parts)}

    if request.authorization:
        updates["authorization"] = {"authorization": request.authorization}

    if request.management is not None:
        updates["management"] = {"management": request.management}

    if request.preferences or request.dealbreakers:
        dealbreakers_str = ", ".join(request.dealbreakers) if request.dealbreakers else ""
        updates["preferences"] = {
            "more_of": request.preferences or "",
            "avoid": dealbreakers_str,
        }

    for step_name, body_data in updates.items():
        existing = (
            await db.execute(
                select(ProfileSection).where(
                    ProfileSection.tenant_id == tenant_id,
                    ProfileSection.step == step_name,
                )
            )
        ).scalar_one_or_none()
        if existing:
            existing.body = body_data
        else:
            new_sec = ProfileSection(
                tenant_id=tenant_id,
                section=step_name,
                step=step_name,
                body=body_data,
                input_mode="text",
            )
            db.add(new_sec)

    await db.flush()
    return {"status": "updated", "saved_sections": list(updates.keys())}


@router.post("/finalize")
async def finalize_counsel(
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Marks counselling complete and moves the candidate to the job hunt (no-op once past it)."""
    from app.domain.journey import get_or_create_journey, set_stage
    journey = await get_or_create_journey(db, tenant_id)
    if journey.stage in ("counsel", "todos", "mailbox"):
        journey = await set_stage(db, tenant_id, "hunt")
    # Commit before scheduling background work: the request's session is only closed after background
    # tasks finish, so an uncommitted write here would hold SQLite's lock against the scan (deadlock).
    await db.commit()
    # The first scan ran when roles were picked, before these facts existed: scan again with them.
    background_tasks.add_task(scan_in_background, tenant_id)
    return {"done": True, "stage": journey.stage}
