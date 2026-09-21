"""Tests for Role Selection & Priority ranking meeting ON-01 and ON-02 specifications."""

import pytest

from app.domain.roles import RoleSelectionError, roles_service


@pytest.mark.asyncio
async def test_on01_fourth_slot_locked_without_mgmt_flag(db_session, sample_tenant):
    """ON-01: 4th role slot is locked unless people/program management experience is indicated."""
    four_roles = [
        "role_fullstack_eng",
        "role_backend_arch",
        "role_frontend_spec",
        "role_product_mgr",
    ]

    # Attempting to save 4 roles without management experience raises RoleSelectionError
    with pytest.raises(RoleSelectionError) as exc_info:
        await roles_service.select_roles(
            session=db_session,
            tenant_id=sample_tenant.id,
            role_ids=four_roles,
            mgmt_experience=False,
        )
    assert "management experience" in str(exc_info.value).lower()

    # With mgmt_experience=True, 4 roles are successfully saved
    saved = await roles_service.select_roles(
        session=db_session,
        tenant_id=sample_tenant.id,
        role_ids=four_roles,
        mgmt_experience=True,
    )
    assert len(saved) == 4
    assert any(r.mgmt_lens for r in saved)


@pytest.mark.asyncio
async def test_on02_priority_persists_across_sessions(db_session, sample_tenant):
    """ON-02: Priority role persists and is assigned rank 1 (weights Scout ranking ×1.5)."""
    selected_ids = [
        "role_fullstack_eng",
        "role_backend_arch",
        "role_frontend_spec",
    ]
    # Explicitly set Backend Architect as the priority role
    await roles_service.select_roles(
        session=db_session,
        tenant_id=sample_tenant.id,
        role_ids=selected_ids,
        priority_role_id="role_backend_arch",
    )
    await db_session.commit()

    # Retrieve roles in a new query
    persisted = await roles_service.get_selected_roles(db_session, sample_tenant.id)
    assert len(persisted) == 3

    # Priority role must have rank 1
    priority_role = persisted[0]
    assert priority_role.rank == 1
    assert priority_role.role_id == "role_backend_arch"
    assert priority_role.title == "Backend Architect"
