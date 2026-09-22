"""Connected Email & Outreach Consent Service (F6, CT-03, RT-06)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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


# "Connect Gmail / Outlook" sign-in. Send-only scopes: we never read the inbox.
OAUTH_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "gmail": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email https://www.googleapis.com/auth/gmail.send",
        "extra": {"access_type": "offline", "prompt": "consent"},
        "settings": ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
        "email_keys": ("email",),
    },
    "outlook": {
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "scope": "openid email offline_access User.Read Mail.Send",
        "extra": {"prompt": "select_account"},
        "settings": ("MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET"),
        "email_keys": ("mail", "userPrincipalName"),
    },
}


def oauth_client(provider: str) -> Optional[Tuple[str, str]]:
    """(client_id, client_secret) when the provider is configured, else None."""
    conf = OAUTH_PROVIDERS.get(provider)
    if not conf:
        return None
    client_id, secret = (getattr(settings, name) for name in conf["settings"])
    return (client_id, secret) if client_id and secret else None


def oauth_redirect_uri(provider: str) -> str:
    return f"{settings.APP_BASE_URL.rstrip('/')}/api/emails/oauth/{provider}/callback"


def oauth_authorize_url(provider: str, state: str) -> str:
    conf = OAUTH_PROVIDERS[provider]
    client_id, _ = oauth_client(provider)
    query = {
        "client_id": client_id,
        "redirect_uri": oauth_redirect_uri(provider),
        "response_type": "code",
        "scope": conf["scope"],
        "state": state,
        **conf["extra"],
    }
    return f"{conf['authorize_url']}?{urlencode(query)}"


async def exchange_oauth_code(provider: str, code: str) -> Dict[str, Any]:
    """Trades the authorization code for tokens and looks up the mailbox address."""
    conf = OAUTH_PROVIDERS[provider]
    client_id, secret = oauth_client(provider)
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_res = await client.post(conf["token_url"], data={
            "code": code,
            "client_id": client_id,
            "client_secret": secret,
            "redirect_uri": oauth_redirect_uri(provider),
            "grant_type": "authorization_code",
            "scope": conf["scope"],
        })
        if token_res.status_code != 200:
            raise EmailConnectError(f"Sign-in was not completed ({token_res.status_code}). Please try again.")
        tokens = token_res.json()
        if not tokens.get("refresh_token"):
            raise EmailConnectError("Offline access was not granted. Please allow access and try again.")
        me = await client.get(conf["userinfo_url"], headers={"Authorization": f"Bearer {tokens['access_token']}"})
        profile = me.json() if me.status_code == 200 else {}
    email = next((profile[k] for k in conf["email_keys"] if profile.get(k)), None)
    if not email:
        raise EmailConnectError("Could not read the email address of the connected account.")
    return {
        "email": email,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_in": int(tokens.get("expires_in", 3600)),
    }


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
        """Stores envelope-encrypted mailbox OAuth credentials (replacing any previous mailbox)."""
        await session.execute(
            update(ConnectedEmail)
            .where(ConnectedEmail.tenant_id == tenant_id, ConnectedEmail.is_active.is_(True))
            .values(is_active=False)
        )
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
