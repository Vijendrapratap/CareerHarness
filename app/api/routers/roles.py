"""Role Catalog & Selection API Router."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.roles import RoleSelectionError, roles_service

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
        await session.commit()
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
