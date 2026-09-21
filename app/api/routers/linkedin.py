"""LinkedIn Intake API Router."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.linkedin import ConsentRequiredError, LinkedInFetchError, linkedin_service

router = APIRouter(prefix="/api/linkedin", tags=["LinkedIn"])


class LinkedInPasteRequest(BaseModel):
    headline: str
    about: str = ""
    experience_entries: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[str]] = None


class LinkedInFetchRequest(BaseModel):
    public_url: str
    user_consented: bool


class LinkedInResponse(BaseModel):
    id: str
    headline: str
    about: str
    source_mode: str
    skills: List[str]


@router.post("/paste", response_model=LinkedInResponse, status_code=status.HTTP_201_CREATED)
async def paste_profile(
    req: LinkedInPasteRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Saves candidate LinkedIn profile via ToS-safe paste mode (F4)."""
    profile = await linkedin_service.save_profile_paste(
        session=session,
        tenant_id=tenant_id,
        headline=req.headline,
        about=req.about,
        experience_entries=req.experience_entries,
        skills=req.skills,
    )
    await session.commit()
    return LinkedInResponse(
        id=profile.id,
        headline=profile.headline,
        about=profile.about,
        source_mode=profile.source_mode,
        skills=profile.skills,
    )


@router.post("/fetch", response_model=LinkedInResponse, status_code=status.HTTP_201_CREATED)
async def fetch_profile(
    req: LinkedInFetchRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Fetches public LinkedIn profile with explicit prior consent tracking (CT-04, LI-01)."""
    try:
        profile = await linkedin_service.fetch_public_profile(
            session=session,
            tenant_id=tenant_id,
            public_url=req.public_url,
            user_consented=req.user_consented,
        )
        await session.commit()
        return LinkedInResponse(
            id=profile.id,
            headline=profile.headline,
            about=profile.about,
            source_mode=profile.source_mode,
            skills=profile.skills,
        )
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LinkedInFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
