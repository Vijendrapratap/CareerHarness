"""Vault and Version Lineage Engine (F10).

Manages immutable document versions, provenance lineage trees,
tailored branches, outcome/conversion tracking, and promote-to-master workflows.
Fulfills VR-01, VR-02, VR-03, and IT-06.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import DocumentVersion


class VaultError(Exception):
    """Base error for Vault operations."""
    pass


class ImmutableDocumentError(VaultError):
    """Raised when an attempt is made to mutate an existing immutable DocumentVersion (VR-02)."""
    pass


class DocumentNotFoundError(VaultError):
    """Raised when a requested DocumentVersion is not found."""
    pass


async def create_initial_master(
    session: AsyncSession,
    tenant_id: str,
    title: str,
    content: Dict[str, Any],
    raw_markdown: str,
    document_type: str = "resume",
) -> DocumentVersion:
    """Create the initial immutable master resume or cover letter for a tenant."""
    # Unset any existing master flag for this document_type
    await session.execute(
        update(DocumentVersion)
        .where(
            DocumentVersion.tenant_id == tenant_id,
            DocumentVersion.document_type == document_type,
            DocumentVersion.is_master.is_(True),
        )
        .values(is_master=False)
    )

    doc_version = DocumentVersion(
        tenant_id=tenant_id,
        document_type=document_type,
        version_number=1,
        title=title,
        content=content,
        raw_markdown=raw_markdown,
        parent_id=None,
        is_master=True,
        is_immutable=True,
        diff_summary={"action": "initial_master_creation"},
    )
    session.add(doc_version)
    await session.flush()
    return doc_version


async def create_tailored_version(
    session: AsyncSession,
    tenant_id: str,
    parent_version_id: str,
    target_job_id: Optional[str],
    target_role_id: Optional[str],
    title: str,
    content: Dict[str, Any],
    raw_markdown: str,
    diff_summary: Optional[Dict[str, Any]] = None,
    document_type: str = "resume",
) -> DocumentVersion:
    """Create a tailored child version branched from a parent version (VR-02)."""
    # Verify parent exists and belongs to tenant
    parent = await get_document_version(session, tenant_id, parent_version_id)
    if not parent:
        raise DocumentNotFoundError(f"Parent version {parent_version_id} not found for tenant {tenant_id}")

    # Determine child version number
    child_version_number = parent.version_number + 1

    child_version = DocumentVersion(
        tenant_id=tenant_id,
        document_type=document_type,
        version_number=child_version_number,
        title=title,
        content=content,
        raw_markdown=raw_markdown,
        parent_id=parent_version_id,
        is_master=False,
        target_role_id=target_role_id,
        target_job_id=target_job_id,
        diff_summary=diff_summary or {},
        is_immutable=True,
    )
    session.add(child_version)
    await session.flush()
    return child_version


async def update_document_version(
    session: AsyncSession,
    tenant_id: str,
    version_id: str,
    **kwargs: Any,
) -> None:
    """Attempting in-place update of an immutable DocumentVersion raises ImmutableDocumentError (VR-02)."""
    doc = await get_document_version(session, tenant_id, version_id)
    if not doc:
        raise DocumentNotFoundError(f"Document version {version_id} not found")
    if doc.is_immutable:
        raise ImmutableDocumentError(
            f"DocumentVersion {version_id} is immutable. Create a new child version instead."
        )


async def promote_to_master(
    session: AsyncSession,
    tenant_id: str,
    version_id: str,
) -> DocumentVersion:
    """Promote a tailored branch to become the new Master resume (VR-03).

    Preserves full provenance/lineage: creates a new master version whose parent_id
    points to the promoted tailored version, and sets is_master=True while demoting previous master.
    """
    source_doc = await get_document_version(session, tenant_id, version_id)
    if not source_doc:
        raise DocumentNotFoundError(f"Version {version_id} not found to promote")

    # Demote current master
    await session.execute(
        update(DocumentVersion)
        .where(
            DocumentVersion.tenant_id == tenant_id,
            DocumentVersion.document_type == source_doc.document_type,
            DocumentVersion.is_master.is_(True),
        )
        .values(is_master=False)
    )

    # Next version number
    new_version_number = source_doc.version_number + 1

    new_master = DocumentVersion(
        tenant_id=tenant_id,
        document_type=source_doc.document_type,
        version_number=new_version_number,
        title=f"Master: {source_doc.title} (Promoted)",
        content=source_doc.content,
        raw_markdown=source_doc.raw_markdown,
        parent_id=source_doc.id,
        is_master=True,
        target_role_id=source_doc.target_role_id,
        target_job_id=None,
        diff_summary={
            "action": "promoted_to_master",
            "promoted_from_version_id": source_doc.id,
            "promoted_from_version_number": source_doc.version_number,
        },
        is_immutable=True,
    )
    session.add(new_master)
    await session.flush()
    return new_master


async def record_outcome(
    session: AsyncSession,
    tenant_id: str,
    version_id: str,
    outcome: str,
) -> DocumentVersion:
    """Record an outcome on a document version (e.g. application, interview, rejection, offer)."""
    doc = await get_document_version(session, tenant_id, version_id)
    if not doc:
        raise DocumentNotFoundError(f"Version {version_id} not found")

    if outcome == "application":
        doc.applications_count += 1
    elif outcome == "interview":
        doc.interviews_count += 1
    elif outcome == "rejection":
        doc.rejections_count += 1
    elif outcome == "offer":
        doc.offers_count += 1
    else:
        raise ValueError(f"Unknown outcome type: {outcome}")

    await session.flush()
    return doc


async def get_document_version(
    session: AsyncSession,
    tenant_id: str,
    version_id: str,
) -> Optional[DocumentVersion]:
    """Retrieve a document version with tenant isolation."""
    stmt = select(DocumentVersion).where(
        DocumentVersion.id == version_id,
        DocumentVersion.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_master_version(
    session: AsyncSession,
    tenant_id: str,
    document_type: str = "resume",
) -> Optional[DocumentVersion]:
    """Retrieve the current active master version for a tenant."""
    stmt = select(DocumentVersion).where(
        DocumentVersion.tenant_id == tenant_id,
        DocumentVersion.document_type == document_type,
        DocumentVersion.is_master.is_(True),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_version_stats(
    session: AsyncSession,
    tenant_id: str,
    version_id: str,
) -> Dict[str, Any]:
    """Calculate aggregated conversion metrics for a specific document version."""
    doc = await get_document_version(session, tenant_id, version_id)
    if not doc:
        raise DocumentNotFoundError(f"Version {version_id} not found")

    interview_rate = 0.0
    if doc.applications_count > 0:
        interview_rate = round((doc.interviews_count / doc.applications_count) * 100, 1)

    return {
        "version_id": doc.id,
        "version_number": doc.version_number,
        "title": doc.title,
        "is_master": doc.is_master,
        "applications_count": doc.applications_count,
        "interviews_count": doc.interviews_count,
        "rejections_count": doc.rejections_count,
        "offers_count": doc.offers_count,
        "interview_conversion_rate": interview_rate,
        "summary_text": f"{doc.applications_count} sends, {doc.interviews_count} interviews ({interview_rate}%)",
    }


async def get_lineage_tree(
    session: AsyncSession,
    tenant_id: str,
    document_type: str = "resume",
) -> List[Dict[str, Any]]:
    """Build the full lineage tree graph for all versions of a document type (IT-06)."""
    stmt = (
        select(DocumentVersion)
        .where(
            DocumentVersion.tenant_id == tenant_id,
            DocumentVersion.document_type == document_type,
        )
        .order_by(DocumentVersion.created_at.asc())
    )
    result = await session.execute(stmt)
    all_versions = list(result.scalars().all())

    # Build node map
    node_map: Dict[str, Dict[str, Any]] = {}
    for doc in all_versions:
        interview_rate = 0.0
        if doc.applications_count > 0:
            interview_rate = round((doc.interviews_count / doc.applications_count) * 100, 1)

        node_map[doc.id] = {
            "id": doc.id,
            "version_number": doc.version_number,
            "title": doc.title,
            "parent_id": doc.parent_id,
            "is_master": doc.is_master,
            "target_role_id": doc.target_role_id,
            "target_job_id": doc.target_job_id,
            "diff_summary": doc.diff_summary,
            "stats": {
                "applications": doc.applications_count,
                "interviews": doc.interviews_count,
                "rejections": doc.rejections_count,
                "offers": doc.offers_count,
                "conversion_rate": interview_rate,
            },
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "children": [],
        }

    # Connect tree
    root_nodes: List[Dict[str, Any]] = []
    for _node_id, node_data in node_map.items():
        parent_id = node_data["parent_id"]
        if parent_id and parent_id in node_map:
            node_map[parent_id]["children"].append(node_data)
        else:
            root_nodes.append(node_data)

    return root_nodes
