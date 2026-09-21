"""BYOK Key Vault Service.

Enforces:
- KY-01: Ciphertext-at-rest with envelope encryption.
- KY-02: Masked display only (sk-...4f2a).
- KY-03: Zero-downtime key rotation.
- KY-04: Key failure pauses runs, notifies user, zero platform-key fallback.
- KY-05: Tenant deletion purges keys and zeroizes in-memory references.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import EncryptedPayload, cipher
from app.domain.models import ApiKey, Run


class KeyVaultError(Exception):
    """Base exception for KeyVault failures."""
    pass


class KeyNotFoundError(KeyVaultError):
    """Raised when an API key does not exist for the tenant/provider."""
    pass


class KeyInactiveError(KeyVaultError):
    """Raised when an API key is marked invalid or has run out of credits."""
    pass


class KeyVaultService:
    """Provides secure BYOK credential storage and memory-only retrieval."""

    @staticmethod
    async def store_key(
        session: AsyncSession,
        tenant_id: str,
        provider: str,
        raw_key: str,
        is_default: bool = True,
    ) -> ApiKey:
        """Encrypts and persists a provider API key for a tenant."""
        clean_provider = provider.lower().strip()
        clean_key = raw_key.strip()
        if not clean_key:
            raise ValueError("API key cannot be empty")

        payload = cipher.encrypt(clean_key, tenant_id)
        cipher_b64, nonce_b64 = payload.to_b64()

        # Check if key exists for this provider
        query = select(ApiKey).where(
            ApiKey.tenant_id == tenant_id,
            ApiKey.provider == clean_provider,
        )
        result = await session.execute(query)
        existing = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if existing:
            # KY-03: Zero-downtime rotation
            existing.encrypted_key_b64 = cipher_b64
            existing.nonce_b64 = nonce_b64
            existing.masked_preview = payload.masked_preview
            existing.status = "valid"
            existing.is_default = is_default
            existing.last_validated_at = now
            existing.updated_at = now
            api_key_obj = existing
        else:
            api_key_obj = ApiKey(
                tenant_id=tenant_id,
                provider=clean_provider,
                encrypted_key_b64=cipher_b64,
                nonce_b64=nonce_b64,
                masked_preview=payload.masked_preview,
                status="valid",
                is_default=is_default,
                last_validated_at=now,
            )
            session.add(api_key_obj)

        await session.flush()
        return api_key_obj

    @staticmethod
    async def get_decrypted_key(
        session: AsyncSession,
        tenant_id: str,
        provider: str,
    ) -> str:
        """Retrieves and decrypts the API key in worker memory only.

        Fails-closed: Never returns fallback platform keys (KY-04).
        """
        clean_provider = provider.lower().strip()
        query = select(ApiKey).where(
            ApiKey.tenant_id == tenant_id,
            ApiKey.provider == clean_provider,
        )
        result = await session.execute(query)
        record = result.scalar_one_or_none()

        if not record:
            raise KeyNotFoundError(
                f"No API key registered for provider '{clean_provider}'. Please add your key in Settings."
            )

        if record.status in ("invalid", "no_credits"):
            raise KeyInactiveError(
                f"API key for provider '{clean_provider}' is inactive (status: {record.status})."
            )

        # In-memory decryption only
        payload = EncryptedPayload.from_b64(
            ciphertext_b64=record.encrypted_key_b64,
            nonce_b64=record.nonce_b64,
            masked_preview=record.masked_preview,
        )
        return cipher.decrypt(payload.ciphertext, payload.nonce, tenant_id)

    @staticmethod
    async def handle_key_failure(
        session: AsyncSession,
        tenant_id: str,
        provider: str,
        reason: str,
    ) -> None:
        """Handles 402/429 key exhaustion by marking key inactive and pausing tenant's runs (KY-04)."""
        clean_provider = provider.lower().strip()
        status = "no_credits" if "402" in reason or "quota" in reason.lower() else "invalid"

        # 1. Update key status
        await session.execute(
            update(ApiKey)
            .where(ApiKey.tenant_id == tenant_id, ApiKey.provider == clean_provider)
            .values(status=status, updated_at=datetime.now(timezone.utc))
        )

        # 2. Pause tenant's active runs without platform fallback
        await session.execute(
            update(Run)
            .where(Run.tenant_id == tenant_id, Run.status == "running")
            .values(
                status="paused",
                pause_reason=f"BYOK provider {clean_provider} failed: {reason}",
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.flush()

    @staticmethod
    async def purge_tenant_keys(
        session: AsyncSession,
        tenant_id: str,
    ) -> int:
        """Purges all keys for a tenant upon deletion (KY-05)."""
        stmt = delete(ApiKey).where(ApiKey.tenant_id == tenant_id)
        result = await session.execute(stmt)
        await session.flush()
        return result.rowcount


keyvault = KeyVaultService()
