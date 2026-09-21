"""Tests for BYOK Key Vault meeting KY-01 through KY-05 specifications."""

import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import select

from app.core.keyvault import KeyInactiveError, keyvault
from app.core.security import EncryptedPayload, cipher, mask_api_key
from app.domain.models import ApiKey, Run


@pytest.mark.asyncio
async def test_ky01_ciphertext_at_rest_and_dek_isolation(db_session, sample_tenant, second_tenant):
    """KY-01: Key ciphertext-at-rest with AES-256-GCM and tenant DEK isolation."""
    raw_key = "sk-proj-test-1234567890-abcdefghijklmnop-secret"

    # Store key in KeyVault
    stored = await keyvault.store_key(
        session=db_session,
        tenant_id=sample_tenant.id,
        provider="openai",
        raw_key=raw_key,
    )

    # 1. Plaintext must NOT appear in encrypted fields
    assert raw_key not in stored.encrypted_key_b64
    assert raw_key not in stored.nonce_b64

    # 2. Key must decrypt cleanly in memory for the owning tenant
    decrypted = await keyvault.get_decrypted_key(
        session=db_session,
        tenant_id=sample_tenant.id,
        provider="openai",
    )
    assert decrypted == raw_key

    # 3. Cross-tenant cryptographic isolation:
    # Attempting to decrypt sample_tenant's ciphertext using second_tenant's DEK must raise InvalidTag
    payload = EncryptedPayload.from_b64(
        stored.encrypted_key_b64, stored.nonce_b64, stored.masked_preview
    )
    with pytest.raises(InvalidTag):
        cipher.decrypt(payload.ciphertext, payload.nonce, tenant_id=second_tenant.id)


@pytest.mark.asyncio
async def test_ky02_masked_display_only(db_session, sample_tenant):
    """KY-02: Key is only ever exposed in masked display form."""
    raw_key = "sk-ant-api03-abcdef1234567890-xyz9"
    stored = await keyvault.store_key(
        session=db_session,
        tenant_id=sample_tenant.id,
        provider="anthropic",
        raw_key=raw_key,
    )

    # Masked preview must match sk-...xyz9
    expected_mask = mask_api_key(raw_key)
    assert stored.masked_preview == expected_mask
    assert stored.masked_preview == "sk-...xyz9"
    assert "abcdef1234567890" not in stored.masked_preview


@pytest.mark.asyncio
async def test_ky03_zero_downtime_key_rotation(db_session, sample_tenant):
    """KY-03: Key rotation updates ciphertext atomically with zero downtime."""
    key_v1 = "sk-initial-key-1111111111111111"
    key_v2 = "sk-rotated-key-2222222222222222"

    # Store version 1
    await keyvault.store_key(db_session, sample_tenant.id, "openai", key_v1)
    decrypted_v1 = await keyvault.get_decrypted_key(db_session, sample_tenant.id, "openai")
    assert decrypted_v1 == key_v1

    # Rotate to version 2
    rotated = await keyvault.store_key(db_session, sample_tenant.id, "openai", key_v2)
    assert rotated.masked_preview == "sk-...2222"

    # Verify version 2 is immediately active
    decrypted_v2 = await keyvault.get_decrypted_key(db_session, sample_tenant.id, "openai")
    assert decrypted_v2 == key_v2


@pytest.mark.asyncio
async def test_ky04_402_injection_pauses_runs_no_fallback(db_session, sample_tenant):
    """KY-04: Provider quota/402 failure marks key inactive, pauses runs, no platform fallback."""
    raw_key = "sk-will-run-out-of-credits-9999"
    await keyvault.store_key(db_session, sample_tenant.id, "openai", raw_key)

    # Create an active agent run for this tenant
    run = Run(
        tenant_id=sample_tenant.id,
        agent_name="scout",
        goal="Search senior backend engineer roles",
        status="running",
    )
    db_session.add(run)
    await db_session.flush()

    # Simulate 402 payment/quota error event
    await keyvault.handle_key_failure(
        session=db_session,
        tenant_id=sample_tenant.id,
        provider="openai",
        reason="HTTP 402: Insufficient quota / payment required",
    )

    # 1. Run must be automatically paused with clear explanation
    await db_session.refresh(run)
    assert run.status == "paused"
    assert "402" in run.pause_reason

    # 2. Key retrieval must fail-closed (no platform key fallback)
    with pytest.raises(KeyInactiveError) as exc_info:
        await keyvault.get_decrypted_key(db_session, sample_tenant.id, "openai")
    assert "no_credits" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ky05_delete_tenant_purges_keys(db_session, sample_tenant):
    """KY-05: Deleting a tenant purges keys from storage."""
    await keyvault.store_key(db_session, sample_tenant.id, "gemini", "aiza-test-key-1234567890-test")

    # Verify key exists
    res = await db_session.execute(
        select(ApiKey).where(ApiKey.tenant_id == sample_tenant.id, ApiKey.provider == "gemini")
    )
    assert res.scalar_one_or_none() is not None

    # Purge keys for tenant
    deleted_count = await keyvault.purge_tenant_keys(db_session, sample_tenant.id)
    assert deleted_count == 1

    # Verify key is completely purged
    res_after = await db_session.execute(
        select(ApiKey).where(ApiKey.tenant_id == sample_tenant.id, ApiKey.provider == "gemini")
    )
    assert res_after.scalar_one_or_none() is None
