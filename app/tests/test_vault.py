"""Unit and contract tests for Vault and Version Lineage Engine (F10).

Tests:
- VR-01: Applications link to an immutable DocumentVersion ID.
- VR-02: Immutable document versions cannot be modified in place.
- VR-03: Promoting tailored branch creates new master version preserving full provenance.
- IT-06: Lineage queries correctly resolve parent-child graph and aggregated conversion stats.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Tenant
from app.domain.vault import (
    ImmutableDocumentError,
    create_initial_master,
    create_tailored_version,
    get_document_version,
    get_lineage_tree,
    get_master_version,
    get_version_stats,
    promote_to_master,
    record_outcome,
    update_document_version,
)


@pytest.mark.asyncio
async def test_vr02_immutable_document_versions_cannot_be_mutated(db_session: AsyncSession):
    """VR-02: Document versions are immutable; in-place edits are strictly rejected."""
    tenant = Tenant(name="Vault User 1", plan="pro")
    db_session.add(tenant)
    await db_session.flush()

    # Create initial master
    master = await create_initial_master(
        session=db_session,
        tenant_id=tenant.id,
        title="Master Resume v1",
        content={"skills": ["Python", "PostgreSQL"], "experience": []},
        raw_markdown="# Master Resume\n- Python\n- PostgreSQL",
    )
    assert master.is_master is True
    assert master.version_number == 1
    assert master.is_immutable is True

    # In-place update must raise ImmutableDocumentError
    with pytest.raises(ImmutableDocumentError) as exc_info:
        await update_document_version(
            session=db_session,
            tenant_id=tenant.id,
            version_id=master.id,
            title="Modified Title",
        )
    assert "is immutable" in str(exc_info.value)

    # Creating a tailored child branch succeeds and assigns parent_id
    tailored = await create_tailored_version(
        session=db_session,
        tenant_id=tenant.id,
        parent_version_id=master.id,
        target_job_id="job-123",
        target_role_id="role-backend",
        title="Tailored for Job 123",
        content={"skills": ["Python", "PostgreSQL", "FastAPI"]},
        raw_markdown="# Tailored\n- Python",
        diff_summary={"added_keywords": ["FastAPI"]},
    )
    assert tailored.parent_id == master.id
    assert tailored.version_number == 2
    assert tailored.is_master is False
    assert tailored.is_immutable is True


@pytest.mark.asyncio
async def test_vr03_promote_to_master_preserves_provenance(db_session: AsyncSession):
    """VR-03: Promoting a tailored branch creates a new master version with full provenance/lineage."""
    tenant = Tenant(name="Vault User 2", plan="free")
    db_session.add(tenant)
    await db_session.flush()

    # 1. Master v1
    master_v1 = await create_initial_master(
        session=db_session,
        tenant_id=tenant.id,
        title="Master Resume v1",
        content={"skills": ["Python"], "experience": [{"company": "Acme", "role": "Dev"}]},
        raw_markdown="Master Resume v1",
    )
    assert master_v1.is_master is True

    # 2. Branch tailored v2
    tailored_v2 = await create_tailored_version(
        session=db_session,
        tenant_id=tenant.id,
        parent_version_id=master_v1.id,
        target_job_id="job-xyz",
        target_role_id="role-lead",
        title="Tailored for XYZ",
        content={"skills": ["Python", "Docker"], "experience": [{"company": "Acme", "role": "Senior Dev"}]},
        raw_markdown="Tailored for XYZ",
    )

    # 3. Promote tailored v2 to become the new master
    master_v3 = await promote_to_master(
        session=db_session,
        tenant_id=tenant.id,
        version_id=tailored_v2.id,
    )

    assert master_v3.is_master is True
    assert master_v3.version_number == 3
    assert master_v3.parent_id == tailored_v2.id
    assert master_v3.diff_summary.get("action") == "promoted_to_master"
    assert master_v3.diff_summary.get("promoted_from_version_id") == tailored_v2.id

    # Verify old master was demoted
    old_master = await get_document_version(db_session, tenant.id, master_v1.id)
    assert old_master.is_master is False

    # Verify get_master_version returns master_v3
    current_master = await get_master_version(db_session, tenant.id)
    assert current_master.id == master_v3.id


@pytest.mark.asyncio
async def test_it06_lineage_graph_and_conversion_metrics(db_session: AsyncSession):
    """IT-06: Lineage tree graph correctly resolves hierarchy and aggregated conversion stats."""
    tenant = Tenant(name="Vault User 3", plan="pro")
    db_session.add(tenant)
    await db_session.flush()

    # Root master
    root = await create_initial_master(
        session=db_session,
        tenant_id=tenant.id,
        title="Root Master",
        content={"skills": ["Go", "Kubernetes"]},
        raw_markdown="Root Master",
    )

    # Branch A
    branch_a = await create_tailored_version(
        session=db_session,
        tenant_id=tenant.id,
        parent_version_id=root.id,
        target_job_id="job-stripe",
        target_role_id=None,
        title="Stripe Tailored",
        content={"skills": ["Go", "Kubernetes", "Kafka"]},
        raw_markdown="Stripe Tailored",
    )

    # Branch B
    branch_b = await create_tailored_version(
        session=db_session,
        tenant_id=tenant.id,
        parent_version_id=root.id,
        target_job_id="job-uber",
        target_role_id=None,
        title="Uber Tailored",
        content={"skills": ["Go", "gRPC"]},
        raw_markdown="Uber Tailored",
    )

    # Record outcomes on Branch A: 3 sends, 1 interview, 1 rejection
    await record_outcome(db_session, tenant.id, branch_a.id, "application")
    await record_outcome(db_session, tenant.id, branch_a.id, "application")
    await record_outcome(db_session, tenant.id, branch_a.id, "application")
    await record_outcome(db_session, tenant.id, branch_a.id, "interview")
    await record_outcome(db_session, tenant.id, branch_a.id, "rejection")

    stats_a = await get_version_stats(db_session, tenant.id, branch_a.id)
    assert stats_a["applications_count"] == 3
    assert stats_a["interviews_count"] == 1
    assert stats_a["rejections_count"] == 1
    assert stats_a["interview_conversion_rate"] == 33.3
    assert "3 sends, 1 interviews" in stats_a["summary_text"]

    # Verify hierarchical lineage tree
    tree = await get_lineage_tree(db_session, tenant.id, "resume")
    assert len(tree) == 1  # 1 root node
    root_node = tree[0]
    assert root_node["id"] == root.id
    assert len(root_node["children"]) == 2  # branch_a and branch_b
    child_ids = {c["id"] for c in root_node["children"]}
    assert branch_a.id in child_ids
    assert branch_b.id in child_ids
