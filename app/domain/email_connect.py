"""Connected Email & Outreach Consent Service (F6, CT-03, RT-06)."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import outbox
from app.core.security import cipher
from app.domain.models import ConnectedEmail, Consent


class EmailConnectError(Exception):
    """Base exception for email connect failures."""
    pass


class OutreachConsentRequiredError(EmailConnectError):
    """Raised when an outreach send is attempted without explicit consent on record (CT-03)."""
    pass


class MailboxTokenExpiredError(EmailConnectError):
    """Raised when the mailbox OAuth token has expired (RT-06)."""
    pass


class EmailConnectService:
    """Manages candidate mailbox OAuth credentials and outreach sending gates."""

    @staticmethod
    async def connect_mailbox(
        session: AsyncSession,
        tenant_id: str,
        email_address: str,
        access_token: str,
        refresh_token: str,
        expires_in_seconds: int = 3600,
        provider: str = "gmail",
    ) -> ConnectedEmail:
        """Stores envelope-encrypted mailbox OAuth credentials."""
        # Encrypt tokens with tenant DEK
        acc_payload = cipher.encrypt(access_token, tenant_id)
        ref_payload = cipher.encrypt(refresh_token, tenant_id)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=expires_in_seconds)

        connected = ConnectedEmail(
            tenant_id=tenant_id,
            provider=provider.lower(),
            email_address=email_address.strip(),
            access_token_encrypted=acc_payload.to_b64()[0],
            refresh_token_encrypted=ref_payload.to_b64()[0],
            token_expires_at=expires_at,
            is_active=True,
        )
        session.add(connected)

        # Emit email.connected event
        await outbox.record_event(
            session=session,
            tenant_id=tenant_id,
            event_name="email.connected",
            payload={"provider": provider, "email": email_address},
        )
        await session.flush()
        return connected

    @staticmethod
    async def grant_outreach_consent(
        session: AsyncSession,
        tenant_id: str,
        ip_address: Optional[str] = None,
    ) -> Consent:
        """Records explicit outreach consent before allowing email sends (CT-03)."""
        consent = Consent(
            tenant_id=tenant_id,
            consent_type="outreach_send",
            granted_at=datetime.now(timezone.utc),
            ip_address=ip_address,
        )
        session.add(consent)
        await session.flush()
        return consent

    @staticmethod
    async def send_outreach_email(
        session: AsyncSession,
        tenant_id: str,
        recipient: str,
        subject: str,
        body: str,
    ) -> dict:
        """Sends an outreach email, strictly verifying prior consent and active OAuth token (CT-03, RT-06)."""
        # 1. CT-03: Consent must precede first send
        consent_q = select(Consent).where(
            Consent.tenant_id == tenant_id,
            Consent.consent_type == "outreach_send",
        )
        consent = (await session.execute(consent_q)).scalar_one_or_none()
        if not consent:
            raise OutreachConsentRequiredError(
                "CT-03: Explicit outreach consent is required before any email can be sent."
            )

        # 2. Check connected email
        email_q = select(ConnectedEmail).where(
            ConnectedEmail.tenant_id == tenant_id,
            ConnectedEmail.is_active.is_(True),
        )
        conn = (await session.execute(email_q)).scalar_one_or_none()
        if not conn:
            raise EmailConnectError("No active connected mailbox found for this tenant.")

        # 3. RT-06: Check token expiration
        now = datetime.now(timezone.utc)
        expires_at = conn.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            raise MailboxTokenExpiredError(
                "RT-06: Mailbox OAuth token has expired. Please re-authenticate to resume."
            )

        # In production, uses SMTP or Gmail API with decrypted token in memory
        return {
            "status": "sent",
            "recipient": recipient,
            "subject": subject,
            "timestamp": now.isoformat(),
        }


email_service = EmailConnectService()
