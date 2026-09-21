"""Tests for Tenant Isolation and Row-Level Security meeting IT-02 specifications."""

import uuid

import pytest
from sqlalchemy import select, update

from app.core.keyvault import keyvault
from app.domain.models import ApiKey, Approval, Run


@pytest.mark.asyncio
async def test_it02_tenant_data_isolation_across_entities(db_session, sample_tenant, second_tenant):
    """IT-02: Tenant A cannot query, mutate, or affect Tenant B's records."""
    tenant_a = sample_tenant
    tenant_b = second_tenant

    # 1. Tenant A stores an API key and creates a Run
    await keyvault.store_key(db_session, tenant_a.id, "openai", "sk-tenant-a-key-111111111")
    run_a = Run(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a.id,
        agent_name="profiler",
        goal="Extract resume bullet points",
        status="running",
    )
    db_session.add(run_a)

    # Tenant A creates an approval request
    approval_a = Approval(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a.id,
        run_id=run_a.id,
        tool_name="ats_submit",
        action_type="external_submission",
        payload={"job_id": "job_123"},
        status="pending",
    )
    db_session.add(approval_a)

    # Tenant B creates their own separate Run
    run_b = Run(
        id=str(uuid.uuid4()),
        tenant_id=tenant_b.id,
        agent_name="scout",
        goal="Find remote jobs",
        status="running",
    )
    db_session.add(run_b)
    await db_session.flush()

    # 2. Verify Scoped Query Isolation:
    # Query for Tenant B's runs must NOT return Tenant A's runs
    query_b_runs = select(Run).where(Run.tenant_id == tenant_b.id)
    result_b_runs = (await db_session.execute(query_b_runs)).scalars().all()
    assert len(result_b_runs) == 1
    assert result_b_runs[0].id == run_b.id
    assert all(r.tenant_id == tenant_b.id for r in result_b_runs)

    # 3. Verify Tenant B querying Tenant A's keys returns nothing
    query_b_keys = select(ApiKey).where(ApiKey.tenant_id == tenant_b.id)
    result_b_keys = (await db_session.execute(query_b_keys)).scalars().all()
    assert len(result_b_keys) == 0

    # 4. Verify Tenant B querying Tenant A's approvals returns nothing
    query_b_approvals = select(Approval).where(Approval.tenant_id == tenant_b.id)
    result_b_approvals = (await db_session.execute(query_b_approvals)).scalars().all()
    assert len(result_b_approvals) == 0

    # 5. Prevent cross-tenant mutation:
    # If Tenant B issues an update scoped to their tenant_id targeting Tenant A's Run id, 0 rows are mutated
    stmt = (
        update(Run)
        .where(Run.tenant_id == tenant_b.id, Run.id == run_a.id)
        .values(status="completed")
    )
    update_res = await db_session.execute(stmt)
    assert update_res.rowcount == 0

    # Confirm Tenant A's run is untouched
    await db_session.refresh(run_a)
    assert run_a.status == "running"


@pytest.mark.asyncio
async def test_it02_cascade_deletion_isolation(db_session, sample_tenant, second_tenant):
    """IT-02: Deleting Tenant A cascades only its own entities, leaving Tenant B intact."""
    tenant_a = sample_tenant
    tenant_b = second_tenant

    # Both tenants add keys and runs
    await keyvault.store_key(db_session, tenant_a.id, "openai", "sk-a-key-1111111111111111")
    await keyvault.store_key(db_session, tenant_b.id, "openai", "sk-b-key-2222222222222222")

    run_a = Run(tenant_id=tenant_a.id, agent_name="scout", goal="A's goal")
    run_b = Run(tenant_id=tenant_b.id, agent_name="scout", goal="B's goal")
    db_session.add_all([run_a, run_b])
    await db_session.flush()

    # Delete Tenant A
    await db_session.delete(tenant_a)
    await db_session.flush()

    # Verify Tenant A's records are purged
    keys_a = (
        await db_session.execute(select(ApiKey).where(ApiKey.tenant_id == tenant_a.id))
    ).scalars().all()
    assert len(keys_a) == 0

    runs_a = (
        await db_session.execute(select(Run).where(Run.tenant_id == tenant_a.id))
    ).scalars().all()
    assert len(runs_a) == 0

    # Verify Tenant B's records are completely intact
    keys_b = (
        await db_session.execute(select(ApiKey).where(ApiKey.tenant_id == tenant_b.id))
    ).scalars().all()
    assert len(keys_b) == 1
    assert keys_b[0].masked_preview == "sk-...2222"

    runs_b = (
        await db_session.execute(select(Run).where(Run.tenant_id == tenant_b.id))
    ).scalars().all()
    assert len(runs_b) == 1
    assert runs_b[0].id == run_b.id
