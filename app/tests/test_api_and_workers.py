"""Tests for FastAPI endpoints and Celery Worker Lanes meeting ST-04 specifications."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.api.main import app
from app.workers.celery_app import QUEUE_LANES, get_queue_for_task


@pytest.fixture
async def api_client(db_session):
    """Provides an AsyncClient connected to the FastAPI application."""
    # Override get_db dependency with test session
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_endpoint(api_client):
    """Verifies public health probe."""
    res = await api_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["app"] == "CareerHarness"


@pytest.mark.asyncio
async def test_api_keys_requires_tenant_header(api_client):
    """Verifies that key management routes fail-closed without X-Tenant-ID header."""
    res = await api_client.post(
        "/api/keys",
        json={"provider": "openai", "api_key": "sk-proj-test12345678"},
    )
    assert res.status_code in (401, 422)  # Missing required header


@pytest.mark.asyncio
async def test_api_keys_lifecycle_and_masked_output(api_client, sample_tenant):
    """Verifies key registration, envelope encryption, and masked response (KY-01, KY-02)."""
    headers = {"X-Tenant-ID": sample_tenant.id}
    raw_key = "sk-proj-supersecret-api-key-12345678"

    # Register key
    res = await api_client.post(
        "/api/keys",
        headers=headers,
        json={"provider": "openai", "api_key": raw_key},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["provider"] == "openai"
    assert data["masked_preview"] == "sk-...5678"
    # Plaintext must not be exposed
    assert raw_key not in res.text

    # List keys
    list_res = await api_client.get("/api/keys", headers=headers)
    assert list_res.status_code == 200
    keys_list = list_res.json()
    assert len(keys_list) == 1
    assert keys_list[0]["masked_preview"] == "sk-...5678"


@pytest.mark.asyncio
async def test_st04_queue_lane_definitions_and_priority_routing():
    """ST-04: Verifies queue lane definitions and priority routing."""
    # 1. Lanes exist and have distinct concurrency limits
    assert "fast" in QUEUE_LANES
    assert "agent_loop" in QUEUE_LANES
    assert "batch" in QUEUE_LANES
    assert QUEUE_LANES["fast"]["concurrency"] > QUEUE_LANES["batch"]["concurrency"]

    # 2. Tasks route to their designated lanes
    assert get_queue_for_task("tasks.validate_key_probe") == "fast"
    assert get_queue_for_task("tasks.publish_outbox_events") == "fast"
    assert get_queue_for_task("tasks.execute_agent_step") == "agent_loop"
    assert get_queue_for_task("tasks.batch_apply_fanout") == "batch"
    assert get_queue_for_task("tasks.scrape_job_board") == "batch"
