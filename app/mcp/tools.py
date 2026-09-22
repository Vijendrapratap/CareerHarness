"""MCP Tool handlers for mailbox and recruiter communication."""

from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.email_connect import email_service
from app.domain.journey import get_or_create_journey, set_stage


class MailboxGateError(Exception):
    """Raised when an outreach send is attempted before the hunt or active stage."""
    pass


async def connect_mailbox(
    tenant_id: str,
    session: AsyncSession,
    email_address: str,
    access_token: str,
    refresh_token: str,
    provider: str = "gmail",
) -> Dict[str, Any]:
    """Connects candidate's mailbox with OAuth tokens."""
    conn = await email_service.connect_mailbox(
        session=session,
        tenant_id=tenant_id,
        email_address=email_address,
        access_token=access_token,
        refresh_token=refresh_token,
        provider=provider,
    )
    return {"status": "connected", "email": conn.email_address}


async def grant_send_consent(tenant_id: str, session: AsyncSession) -> Dict[str, Any]:
    """Records candidate consent and advances stage if mailbox is connected."""
    consent = await email_service.grant_outreach_consent(
        session=session,
        tenant_id=tenant_id,
    )
    journey = await get_or_create_journey(session, tenant_id)
    if journey.stage == "mailbox":
        await set_stage(session, tenant_id, "hunt")
    return {"status": "granted", "consent_type": consent.consent_type}


async def queue_recruiter_email(
    tenant_id: str,
    session: AsyncSession,
    recipient: str,
    subject: str,
    body: str,
) -> Dict[str, Any]:
    """Sends recruiter email via connected mailbox only when stage is hunt or active."""
    journey = await get_or_create_journey(session, tenant_id)
    if journey.stage not in ("hunt", "active"):
        raise MailboxGateError("Connect the mailbox after the to-do list is clear.")

    return await email_service.send_outreach_email(
        session=session,
        tenant_id=tenant_id,
        recipient=recipient,
        subject=subject,
        body=body,
    )
