"""Integration tests for Phase 2 Discovery & Batch API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.api.main import app
from app.domain.jobs import job_service


@pytest.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_discovery_and_batch_api_pipeline(client, sample_tenant, db_session):
    """Verifies end-to-end API pipeline for email connect, job ingest, and batch application."""
    headers = {"X-Tenant-ID": sample_tenant.id}

    # 1. Connect Email Mailbox (F6)
    email_res = await client.post(
        "/api/emails/connect",
        headers=headers,
        json={
            "email_address": "candidate@example.com",
            "access_token": "tok_access",
            "refresh_token": "tok_refresh",
            "provider": "gmail",
        },
    )
    assert email_res.status_code == 201
    assert email_res.json()["status"] == "connected"

    # 2. Grant Outreach Consent (CT-03)
    consent_res = await client.post("/api/emails/consent", headers=headers)
    assert consent_res.status_code == 201

    # 3. Ingest 2 Jobs (F8)
    j1 = await job_service.ingest_job(
        session=db_session,
        title="Senior Distributed Systems Engineer",
        company="DataCorp",
        url="https://jobs.lever.co/datacorp/123",
        description="Scaling distributed storage clusters and high-volume data streaming pipelines.",
    )
    j2 = await job_service.ingest_job(
        session=db_session,
        title="Staff Backend Architect",
        company="CloudNet",
        url="https://boards.greenhouse.io/cloudnet/456",
        description="Designing event-driven architecture and real-time API gateways.",
    )
    await db_session.commit()

    # 4. Create Batch Apply Group (F8, BA-01)
    batch_res = await client.post(
        "/api/batches",
        headers=headers,
        json={"job_ids": [j1.id, j2.id]},
    )
    assert batch_res.status_code == 201
    batch_id = batch_res.json()["batch_id"]

    # 5. Get Batch Preview (BA-04)
    preview_res = await client.get(f"/api/batches/{batch_id}/preview", headers=headers)
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert preview["total_jobs"] == 2
    assert len(preview["items"]) == 2

    # 6. Approve Batch
    app_res = await client.post(f"/api/batches/{batch_id}/approve", headers=headers)
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"

    # 7. Execute Batch (BA-01..03)
    exec_res = await client.post(f"/api/batches/{batch_id}/execute", headers=headers)
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "completed"
