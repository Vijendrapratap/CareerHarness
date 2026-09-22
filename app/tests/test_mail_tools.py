import pytest

from app.domain.journey import set_stage
from app.mcp.tools import MailboxGateError, queue_recruiter_email


@pytest.mark.asyncio
async def test_recruiter_email_is_refused_before_the_mailbox_stage(db_session, sample_tenant):
    await set_stage(db_session, sample_tenant.id, "todos")
    with pytest.raises(MailboxGateError):
        await queue_recruiter_email(
            sample_tenant.id, db_session, "jobs@acme.com", "Application", "Hello"
        )
