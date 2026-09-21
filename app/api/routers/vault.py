"""API router for Vault and Version Lineage (F10)."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.vault import (
    DocumentNotFoundError,
    ImmutableDocumentError,
    create_initial_master,
    create_tailored_version,
    get_lineage_tree,
    get_master_version,
    get_version_stats,
    promote_to_master,
    record_outcome,
    update_document_version,
)

router = APIRouter(prefix="/api/vault", tags=["Vault"])


class MasterDocumentCreateRequest(BaseModel):
    title: str = Field(default="Master Resume")
    content: Dict[str, Any]
    raw_markdown: str = ""
    document_type: str = "resume"


class TailoredDocumentCreateRequest(BaseModel):
    parent_version_id: str
    target_job_id: Optional[str] = None
    target_role_id: Optional[str] = None
    title: str
    content: Dict[str, Any]
    raw_markdown: str = ""
    diff_summary: Dict[str, Any] = Field(default_factory=dict)
    document_type: str = "resume"


class PromoteMasterRequest(BaseModel):
    version_id: str


class RecordOutcomeRequest(BaseModel):
    version_id: str
    outcome: str  # application, interview, rejection, offer


@router.post("/master")
async def create_master_endpoint(
    req: MasterDocumentCreateRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create initial master document version for tenant."""
    doc = await create_initial_master(
        session=session,
        tenant_id=tenant_id,
        title=req.title,
        content=req.content,
        raw_markdown=req.raw_markdown,
        document_type=req.document_type,
    )
    return {
        "id": doc.id,
        "version_number": doc.version_number,
        "title": doc.title,
        "is_master": doc.is_master,
        "is_immutable": doc.is_immutable,
    }


@router.get("/master")
async def get_master_endpoint(
    document_type: str = "resume",
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get active master document."""
    doc = await get_master_version(session, tenant_id, document_type)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No master document found")
    return {
        "id": doc.id,
        "version_number": doc.version_number,
        "title": doc.title,
        "content": doc.content,
        "is_master": doc.is_master,
    }


@router.post("/tailor")
async def create_tailored_endpoint(
    req: TailoredDocumentCreateRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create an immutable tailored child version from parent (VR-02)."""
    try:
        doc = await create_tailored_version(
            session=session,
            tenant_id=tenant_id,
            parent_version_id=req.parent_version_id,
            target_job_id=req.target_job_id,
            target_role_id=req.target_role_id,
            title=req.title,
            content=req.content,
            raw_markdown=req.raw_markdown,
            diff_summary=req.diff_summary,
            document_type=req.document_type,
        )
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return {
        "id": doc.id,
        "version_number": doc.version_number,
        "parent_id": doc.parent_id,
        "title": doc.title,
        "is_master": doc.is_master,
    }


@router.put("/versions/{version_id}")
async def update_version_endpoint(
    version_id: str,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Attempting in-place update of immutable document version returns error (VR-02)."""
    try:
        await update_document_version(session, tenant_id, version_id)
        return {"status": "ok"}
    except ImmutableDocumentError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/promote")
async def promote_to_master_endpoint(
    req: PromoteMasterRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Promote tailored branch to new master version (VR-03)."""
    try:
        new_master = await promote_to_master(session, tenant_id, req.version_id)
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return {
        "id": new_master.id,
        "version_number": new_master.version_number,
        "parent_id": new_master.parent_id,
        "title": new_master.title,
        "is_master": new_master.is_master,
        "diff_summary": new_master.diff_summary,
    }


@router.post("/outcomes")
async def record_outcome_endpoint(
    req: RecordOutcomeRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Record application outcome on document version."""
    try:
        doc = await record_outcome(session, tenant_id, req.version_id, req.outcome)
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return {
        "version_id": doc.id,
        "applications": doc.applications_count,
        "interviews": doc.interviews_count,
        "rejections": doc.rejections_count,
        "offers": doc.offers_count,
    }


@router.get("/versions/{version_id}/stats")
async def get_version_stats_endpoint(
    version_id: str,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get aggregated conversion stats for version."""
    try:
        return await get_version_stats(session, tenant_id, version_id)
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/lineage")
async def get_lineage_endpoint(
    document_type: str = "resume",
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get full lineage tree graph for tenant documents (IT-06)."""
    return await get_lineage_tree(session, tenant_id, document_type)
