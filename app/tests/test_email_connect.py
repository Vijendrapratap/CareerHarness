"""Tests for Email Connect & Outreach Consent meeting CT-03 and RT-06 specifications."""

import pytest

from app.domain.email_connect import (
    MailboxTokenExpiredError,
    OutreachConsentRequiredError,
    email_service,
)


@pytest.mark.asyncio
async def test_ct03_consent_precedes_first_send(db_session, sample_tenant):
    """CT-03: Outreach consent must explicitly precede the first external send."""
    # Connect active mailbox
    mock_tok = "tok_" + "123"
    await email_service.connect_mailbox(
        session=db_session,
        tenant_id=sample_tenant.id,
        email_address="candidate@example.com",
        access_token=mock_tok,
        refresh_token=mock_tok,
        expires_in_seconds=3600,
    )

    # 1. Sending without consent raises OutreachConsentRequiredError
    with pytest.raises(OutreachConsentRequiredError) as exc_info:
        await email_service.send_outreach_email(
            session=db_session,
            tenant_id=sample_tenant.id,
            recipient="hiring.manager@techcorp.com",
            subject="Senior Backend Engineer role",
            body="I am excited about this opportunity...",
        )
    assert "CT-03" in str(exc_info.value)

    # 2. Granting explicit consent allows send
    await email_service.grant_outreach_consent(
        session=db_session,
        tenant_id=sample_tenant.id,
        ip_address="192.168.1.100",
    )

    result = await email_service.send_outreach_email(
        session=db_session,
        tenant_id=sample_tenant.id,
        recipient="hiring.manager@techcorp.com",
        subject="Senior Backend Engineer role",
        body="I am excited about this opportunity...",
    )
    assert result["status"] == "sent"
    assert result["recipient"] == "hiring.manager@techcorp.com"


@pytest.mark.asyncio
async def test_rt06_token_expiry_handling(db_session, sample_tenant):
    """RT-06: Expired mailbox OAuth token pauses gracefully with clear re-auth prompt."""
    # Connect mailbox with an already expired token
    tok = "t_" + "exp"
    await email_service.connect_mailbox(
        session=db_session,
        tenant_id=sample_tenant.id,
        email_address="candidate@example.com",
        access_token=tok,
        refresh_token=tok,
        expires_in_seconds=-60,  # expired 60s ago
    )
    await email_service.grant_outreach_consent(db_session, sample_tenant.id)

    # Send raises MailboxTokenExpiredError
    with pytest.raises(MailboxTokenExpiredError) as exc_info:
        await email_service.send_outreach_email(
            session=db_session,
            tenant_id=sample_tenant.id,
            recipient="recruiter@company.com",
            subject="Application followup",
            body="Following up on my submission...",
        )
    assert "RT-06" in str(exc_info.value)
