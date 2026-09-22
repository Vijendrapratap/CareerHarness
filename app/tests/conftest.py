"""Pytest fixtures for CareerHarness test suite."""

import asyncio
import os
import uuid
from typing import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.domain.models import Base, Tenant

# Set test environment
os.environ["ENVIRONMENT"] = "testing"
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def sample_tenant(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name="Test Candidate Corp",
        plan="pro",
        trusted_mode=False,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def second_tenant(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name="Other Candidate Ltd",
        plan="free",
        trusted_mode=False,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture(autouse=True)
def no_background_scout(monkeypatch):
    """Role selection starts a real network scan in production; tests never do."""

    async def _noop(tenant_id: str) -> None:
        return None

    monkeypatch.setattr("app.api.routers.roles.start_scout_in_background", _noop)
