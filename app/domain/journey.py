from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import CandidateJourney

Stage = Literal["counsel", "todos", "mailbox", "hunt", "active"]
_ORDER = ("counsel", "todos", "mailbox", "hunt", "active")


class JourneyRegressionError(Exception):
    pass


async def get_or_create_journey(session: AsyncSession, tenant_id: str) -> CandidateJourney:
    row = (
        await session.execute(select(CandidateJourney).where(CandidateJourney.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if row:
        return row
    row = CandidateJourney(tenant_id=tenant_id, stage="counsel")
    session.add(row)
    await session.flush()
    return row


async def set_stage(session: AsyncSession, tenant_id: str, stage: Stage) -> CandidateJourney:
    row = await get_or_create_journey(session, tenant_id)
    if _ORDER.index(stage) < _ORDER.index(row.stage):
        raise JourneyRegressionError(f"Cannot move from {row.stage} back to {stage}.")
    row.stage = stage
    await session.flush()
    return row
