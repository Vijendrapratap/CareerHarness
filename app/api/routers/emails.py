"""Email Connect & Outreach Consent API Router (F6)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_tenant_id
from app.domain.email_connect import (
    EmailConnectError,
    MailboxTokenExpiredError,
    OutreachConsentRequiredError,
    email_service,
)

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
