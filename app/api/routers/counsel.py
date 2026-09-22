"""Counsellor API Router (Task 4)."""

from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.counsel import (
    CounselOrderError,
    CounselValidationError,
    get_counsel_state,
    record_answer,
)
from app.domain.roles import RoleSelectionError

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
    import os
    import httpx
    from sqlalchemy import select
    from app.core.keyvault import KeyVaultService
    from app.domain.journey import get_or_create_journey
    from app.domain.models import ProfileSection

    message = request.message.strip()
    history = request.history
    context = request.context or {}

    # Extract detected attributes from message
    detected: dict = {}
    lower_msg = message.lower()

    # Leadership / Management detection
    if any(term in lower_msg for term in ["manage", "lead team", "lead squads", "engineering manager", "head of", "director"]):
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

    # Persist detected dimensions into ProfileSection upsert
    for sec_step, sec_val in detected.items():
        existing_sec = (
            await db.execute(
                select(ProfileSection).where(
                    ProfileSection.tenant_id == tenant_id,
                    ProfileSection.step == sec_step,
                )
            )
        ).scalar_one_or_none()
        body_val = sec_val if isinstance(sec_val, dict) else {"raw": sec_val, "value": sec_val}
        if existing_sec:
            existing_sec.body = body_val
        else:
            new_sec = ProfileSection(
                tenant_id=tenant_id,
                section=sec_step,
                step=sec_step,
                body=body_val,
                input_mode="text",
            )
            db.add(new_sec)
    await db.flush()

    # Try calling OpenRouter with DeepSeek Flash / Chat
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        try:
            api_key = await KeyVaultService.get_decrypted_key(db, tenant_id, "openrouter")
        except Exception:
            api_key = None

    reply = ""
    if api_key and not api_key.startswith("sk-test-"):
        try:
            target_roles = context.get("target_roles", [])
            resume_skills = context.get("skills", [])
            linkedin = context.get("linkedin", "None")

            system_prompt = (
                "You are the CareerHarness AI Executive Career Counsellor.\n"
                "Your objective is to have a focused, encouraging, high-impact conversation with the candidate "
                "to build a strong, precise candidate persona for our autonomous Scout job search agent.\n\n"
                f"Candidate Context so far:\n"
                f"- Target Roles: {', '.join(target_roles) if target_roles else 'Software Engineer'}\n"
                f"- Extracted Resume Skills: {', '.join(resume_skills[:12]) if resume_skills else 'Extracted from resume'}\n"
                f"- LinkedIn Profile: {linkedin}\n\n"
                "Key dimensions to confirm and calibrate across the chat:\n"
                "1. Technical superpowers & favorite problem spaces\n"
                "2. Leadership scope (Senior IC vs Team Lead / Manager)\n"
                "3. Work location & setup (Remote, Hybrid, Cities)\n"
                "4. Work authorization & visa sponsorship status\n"
                "5. Culture & technical dealbreakers (e.g. legacy monoliths, 24/7 on-call, company stages)\n\n"
                "Style rules:\n"
                "- Speak like a seasoned Silicon Valley executive career strategist and job scout.\n"
                "- Directly answer the candidate's questions and give expert guidance on how to position their resume and target roles for the current market.\n"
                "- Do NOT interrogate the candidate with endless questions or forced steps.\n"
                "- Provide high-value strategic insight in 1-2 concise paragraphs and confirm their profile is well-calibrated for Scout."
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
                        "model": "deepseek/deepseek-chat-v4.1",
                        "messages": messages_payload,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    reply = data["choices"][0]["message"]["content"].strip()
        except Exception:
            reply = ""

    # Intelligent Fallback if LLM request times out or no key is present
    if not reply:
        if "management" in detected:
            if detected["management"]:
                reply = (
                    "Leadership experience confirmed! I've flagged your profile for Engineering Manager and Squad Lead tracks, "
                    "unlocking broader search scopes and executive recruiter outreach. Your candidate persona is looking sharp."
                )
            else:
                reply = (
                    "Individual Contributor (IC) track confirmed! We will focus 100% on Senior, Staff, and Principal engineering "
                    "roles prioritizing technical ownership, systems architecture, and high leverage execution."
                )
        elif "location" in detected or "authorization" in detected or "preferences" in detected:
            reply = (
                "Preferences recorded and saved to your profile! Scout will filter out misaligned vacancies and prioritize "
                "roles matching your exact criteria. You can adjust preferences anytime below or proceed directly to your matched jobs."
            )
        else:
            reply = (
                "I've analyzed your target roles and resume skills. Based on current market signals, you have strong positioning "
                "for senior engineering opportunities. You can fine-tune your search preferences below or click 'Complete & Scout My Jobs' to proceed."
            )

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
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Marks counselling complete and unlocks the todos stage."""
    from app.domain.journey import set_stage
    await set_stage(db, tenant_id, "todos")
    return {"done": True, "stage": "todos"}
