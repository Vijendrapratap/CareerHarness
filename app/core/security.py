"""Cryptographic primitives and Envelope Encryption for BYOK Key Vault."""

import base64
import os
import re
from dataclasses import dataclass
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

# Regex to scrub sensitive API keys from logs and exceptions
KEY_PATTERN = re.compile(r"(sk-[a-zA-Z0-9_\-]{16,}|anthropic-[a-zA-Z0-9_\-]{16,}|aiza[a-zA-Z0-9_\-]{20,})")


def mask_api_key(raw_key: str) -> str:
    """Masks an API key for safe display (e.g. sk-...4f2a).

    Guarantees that plaintext is never exposed in UI or logs (KY-02).
    """
    if not raw_key:
        return ""
    clean = raw_key.strip()
    if len(clean) <= 8:
        return "****"
    prefix = clean[:3]
    suffix = clean[-4:]
    return f"{prefix}...{suffix}"


def sanitize_log(message: str) -> str:
    """Removes any inadvertently exposed raw API keys from log strings."""
    return KEY_PATTERN.sub(lambda m: mask_api_key(m.group(0)), message)


@dataclass(frozen=True)
class EncryptedPayload:
    ciphertext: bytes
    nonce: bytes
    masked_preview: str

    def to_b64(self) -> tuple[str, str]:
        """Returns base64 encoded strings for DB persistence."""
        return (
            base64.b64encode(self.ciphertext).decode("ascii"),
            base64.b64encode(self.nonce).decode("ascii"),
        )

    @classmethod
    def from_b64(cls, ciphertext_b64: str, nonce_b64: str, masked_preview: str) -> "EncryptedPayload":
        return cls(
            ciphertext=base64.b64decode(ciphertext_b64),
            nonce=base64.b64decode(nonce_b64),
            masked_preview=masked_preview,
        )


class EnvelopeCipher:
    """Implements envelope encryption with AES-256-GCM and HKDF DEK derivation.

    Enforces:
    - KY-01: Ciphertext-at-rest with AES-256-GCM.
    - Isolation: Per-tenant Data Encryption Key (DEK) derived from master key + tenant_id.
    - Zero-leakage: In-memory decryption only; keys never persisted in plaintext.
    """

    def __init__(self, master_key_b64: Optional[str] = None):
        raw_master = master_key_b64 or settings.MASTER_KEY
        try:
            self._master_key = base64.b64decode(raw_master)
            if len(self._master_key) < 32:
                # Pad to 32 bytes if necessary
                self._master_key = self._master_key.ljust(32, b"\0")
        except Exception:
            # Fallback to UTF-8 encoded bytes padded/hashed to 32 bytes
            digest = hashes.Hash(hashes.SHA256())
            digest.update(raw_master.encode("utf-8"))
            self._master_key = digest.finalize()

    def derive_tenant_dek(self, tenant_id: str) -> bytes:
        """Derives a per-tenant 256-bit Data Encryption Key using HKDF-SHA256."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=tenant_id.encode("utf-8"),
            info=b"career-harness-tenant-dek-v1",
        )
        return hkdf.derive(self._master_key)

    def encrypt(self, raw_plaintext: str, tenant_id: str) -> EncryptedPayload:
        """Encrypts plaintext string with tenant's derived DEK."""
        if not raw_plaintext:
            raise ValueError("Plaintext key cannot be empty")

        dek = self.derive_tenant_dek(tenant_id)
        aesgcm = AESGCM(dek)
        nonce = os.urandom(12)  # Standard 96-bit (12 bytes) GCM nonce
        data = raw_plaintext.strip().encode("utf-8")
        # Associated authenticated data binds ciphertext to this exact tenant_id
        aad = tenant_id.encode("utf-8")

        ciphertext = aesgcm.encrypt(nonce, data, aad)
        masked = mask_api_key(raw_plaintext)

        return EncryptedPayload(
            ciphertext=ciphertext,
            nonce=nonce,
            masked_preview=masked,
        )

    def decrypt(self, ciphertext: bytes, nonce: bytes, tenant_id: str) -> str:
        """Decrypts ciphertext with tenant's derived DEK. Plaintext kept in worker memory only."""
        dek = self.derive_tenant_dek(tenant_id)
        aesgcm = AESGCM(dek)
        aad = tenant_id.encode("utf-8")

        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, aad)
        return plaintext_bytes.decode("utf-8")


cipher = EnvelopeCipher()
