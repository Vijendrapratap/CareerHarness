"""Role Catalog & Selection API Router."""

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.fit_service import evaluate_tenant
from app.domain.roles import RoleSelectionError, roles_service
from app.domain.scout import start_scout_in_background

router = APIRouter(prefix="/api/roles", tags=["Roles"])


class RoleSelectRequest(BaseModel):
    role_ids: List[str]
    mgmt_experience: bool = False
    priority_role_id: Optional[str] = None


class RoleItemResponse(BaseModel):
    id: str
    role_id: str
    title: str
    rank: int
    mgmt_lens: bool


@router.get("/catalog")
async def get_role_catalog():
    """Returns available target roles grouped by family."""
    return roles_service.get_catalog()


@router.get("/suggest")
async def suggest_roles(background: str, mgmt_experience: bool = False):
    """Returns two or three roles that match a background, plus a leadership slot when earned."""
    return roles_service.suggest_roles(background, mgmt_experience=mgmt_experience)


@router.get("", response_model=List[RoleItemResponse])
async def get_selected_roles(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves candidate selected target roles in priority order (ON-02)."""
    roles = await roles_service.get_selected_roles(session, tenant_id)
    return [
        RoleItemResponse(
            id=r.id,
            role_id=r.role_id,
            title=r.title,
            rank=r.rank,
            mgmt_lens=r.mgmt_lens,
        )
        for r in roles
    ]


@router.post("", response_model=List[RoleItemResponse], status_code=status.HTTP_201_CREATED)
async def select_roles(
    req: RoleSelectRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Sets candidate target roles (max 3 without mgmt, 4th unlocked with mgmt) (ON-01)."""
    try:
        selections = await roles_service.select_roles(
            session=session,
            tenant_id=tenant_id,
            role_ids=req.role_ids,
            mgmt_experience=req.mgmt_experience,
            priority_role_id=req.priority_role_id,
        )
        await evaluate_tenant(session, tenant_id)  # role alignment changes every job's fit
        await session.commit()
        # Scouting starts as soon as roles are chosen (after the response is sent).
        background_tasks.add_task(start_scout_in_background, tenant_id)
        return [
            RoleItemResponse(
                id=s.id,
                role_id=s.role_id,
                title=s.title,
                rank=s.rank,
                mgmt_lens=s.mgmt_lens,
            )
            for s in selections
        ]
    except RoleSelectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
