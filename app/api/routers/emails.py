"""Email Connect & Outreach Consent API Router (F6)."""

from datetime import timedelta
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.core.auth import create_access_token, decode_access_token
from app.domain.email_connect import (
    OAUTH_PROVIDERS,
    EmailConnectError,
    MailboxTokenExpiredError,
    OutreachConsentRequiredError,
    email_service,
    exchange_oauth_code,
    oauth_authorize_url,
    oauth_client,
)
from app.domain.models import ConnectedEmail

router = APIRouter(prefix="/api/emails", tags=["Email & Outreach"])


class EmailConnectRequest(BaseModel):
    email_address: str
    access_token: str
    refresh_token: str
    expires_in_seconds: int = 3600
    provider: str = "gmail"


class OutreachSendRequest(BaseModel):
    recipient: str
    subject: str
    body: str


@router.post("/connect", status_code=status.HTTP_201_CREATED)
async def connect_email(
    req: EmailConnectRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Stores encrypted OAuth mailbox credentials (F6)."""
    conn = await email_service.connect_mailbox(
        session=session,
        tenant_id=tenant_id,
        email_address=req.email_address,
        access_token=req.access_token,
        refresh_token=req.refresh_token,
        expires_in_seconds=req.expires_in_seconds,
        provider=req.provider,
    )
    await session.commit()
    return {"status": "connected", "email": conn.email_address, "provider": conn.provider}


@router.post("/consent", status_code=status.HTTP_201_CREATED)
async def grant_consent(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Records explicit consent for agent outreach sends (CT-03)."""
    consent = await email_service.grant_outreach_consent(session, tenant_id)
    await session.commit()
    return {"status": "consent_recorded", "granted_at": consent.granted_at}


@router.post("/send")
async def send_outreach(
    req: OutreachSendRequest,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Sends candidate outreach email (CT-03, RT-06)."""
    try:
        result = await email_service.send_outreach_email(
            session=session,
            tenant_id=tenant_id,
            recipient=req.recipient,
            subject=req.subject,
            body=req.body,
        )
        await session.commit()
        return result
    except OutreachConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except MailboxTokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except EmailConnectError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _back_to_mailbox(**params: str) -> RedirectResponse:
    query = "&".join(f"{k}={quote(v)}" for k, v in params.items())
    return RedirectResponse(f"/mailbox?{query}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/status")
async def email_status(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Which sign-in providers are configured, and the currently connected mailbox (if any)."""
    conn = (await session.execute(
        select(ConnectedEmail).where(ConnectedEmail.tenant_id == tenant_id, ConnectedEmail.is_active.is_(True))
    )).scalars().first()
    return {
        "providers": {p: oauth_client(p) is not None for p in OAUTH_PROVIDERS},
        "connected": {"email": conn.email_address, "provider": conn.provider} if conn else None,
    }


@router.get("/oauth/{provider}/start")
async def oauth_start(provider: str, tenant_id: str = Depends(get_tenant_id)):
    """Step 1 of "Connect Gmail/Outlook": send the candidate to the provider's sign-in page."""
    if oauth_client(provider) is None:
        return _back_to_mailbox(error=f"{provider.title()} sign-in is not configured yet.")
    state = create_access_token(
        {"purpose": "mail_oauth", "tenant_id": tenant_id, "provider": provider}, timedelta(minutes=10)
    )
    return RedirectResponse(oauth_authorize_url(provider, state), status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    state: str,
    code: Optional[str] = None,
    error: Optional[str] = None,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db),
):
    """Step 2: the provider sends the candidate back; store the mailbox and their send consent."""
    if error or not code:
        return _back_to_mailbox(error="Sign-in was cancelled.")
    try:
        claims = decode_access_token(state)
    except Exception:
        return _back_to_mailbox(error="Sign-in link expired. Please try again.")
    if claims.get("purpose") != "mail_oauth" or claims.get("tenant_id") != tenant_id or claims.get("provider") != provider:
        return _back_to_mailbox(error="Sign-in did not match your session. Please try again.")
    try:
        account = await exchange_oauth_code(provider, code)
    except EmailConnectError as exc:
        return _back_to_mailbox(error=str(exc))

    await email_service.connect_mailbox(
        session=session,
        tenant_id=tenant_id,
        email_address=account["email"],
        access_token=account["access_token"],
        refresh_token=account["refresh_token"],
        expires_in_seconds=account["expires_in"],
        provider=provider,
    )
    # Connecting is the consent step: the button states that approved emails are sent from this inbox.
    await email_service.grant_outreach_consent(session, tenant_id)
    await session.commit()
    return _back_to_mailbox(connected=provider)
