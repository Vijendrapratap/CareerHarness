"""Scout starts on role selection; email outreach is optional and connects via OAuth."""

import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.api.main import app
from app.core.config import settings
from app.domain.journey import get_or_create_journey
from app.domain.models import ConnectedEmail, Consent, JobListing, JobMatch
from app.domain.roles import roles_service
from app.domain.scout import run_scout, scout_scheduler


@pytest.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _boards_transport():
    greenhouse = {"jobs": [
        {"id": 1, "title": "Senior Software Engineer, Full Stack", "absolute_url": "https://gh/acme/1",
         "location": {"name": "Remote"}, "content": "x" * 400},
        {"id": 2, "title": "Account Executive", "absolute_url": "https://gh/acme/2",
         "location": {"name": "NYC"}, "content": "x" * 400},
    ]}
    ashby = {"jobs": [
        {"id": "a", "title": "Backend Engineer, Payments", "jobUrl": "https://ashby/zeta/a",
         "location": "Remote", "descriptionPlain": "y" * 400},
    ]}

    def handler(request: httpx.Request) -> httpx.Response:
        if "greenhouse" in str(request.url):
            return httpx.Response(200, text=json.dumps(greenhouse))
        if "ashby" in str(request.url):
            return httpx.Response(200, text=json.dumps(ashby))
        return httpx.Response(404)

    return httpx.MockTransport(handler)


BOARDS = [{"portal": "greenhouse", "org": "acme"}, {"portal": "ashby", "org": "zeta"}]


@pytest.mark.asyncio
async def test_run_scout_keeps_only_role_matches_and_dedupes(db_session, sample_tenant):
    await roles_service.select_roles(
        db_session, sample_tenant.id, ["role_fullstack_eng", "role_backend_arch"], priority_role_id="role_fullstack_eng"
    )
    async with httpx.AsyncClient(transport=_boards_transport()) as c:
        first = await run_scout(db_session, sample_tenant.id, boards=BOARDS, client=c)
        second = await run_scout(db_session, sample_tenant.id, boards=BOARDS, client=c)

    assert first["new_matches"] == 2  # Account Executive filtered out
    assert second["new_matches"] == 0  # re-scan does not duplicate
    matches = (await db_session.execute(
        select(JobMatch).where(JobMatch.tenant_id == sample_tenant.id).order_by(JobMatch.match_score.desc())
    )).scalars().all()
    assert len(matches) == 2
    assert "Full Stack Engineer" in matches[0].why_matched  # priority role ranks first
    assert matches[0].match_score > matches[1].match_score


@pytest.mark.asyncio
async def test_manual_scan_not_blocked_by_readiness(db_session, sample_tenant):
    res = await scout_scheduler.trigger_manual_scan(db_session, sample_tenant.id)
    assert res["status"] == "scout_started"


@pytest.mark.asyncio
async def test_selecting_roles_starts_scout(client, sample_tenant, monkeypatch):
    started = []
    monkeypatch.setattr("app.api.routers.roles.start_scout_in_background", lambda tid: started.append(tid))
    res = await client.post(
        "/api/roles", headers={"X-Tenant-ID": sample_tenant.id}, json={"role_ids": ["role_fullstack_eng"]}
    )
    assert res.status_code == 201
    assert started == [sample_tenant.id]


@pytest.mark.asyncio
async def test_finalize_counsel_goes_straight_to_hunt(client, db_session, sample_tenant):
    res = await client.post("/api/counsel/finalize", headers={"X-Tenant-ID": sample_tenant.id})
    assert res.json()["stage"] == "hunt"
    assert (await get_or_create_journey(db_session, sample_tenant.id)).stage == "hunt"


# --- Email OAuth ---------------------------------------------------------------


@pytest.fixture
def google_configured(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "gid.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "gsecret")
    monkeypatch.setattr(settings, "MICROSOFT_CLIENT_ID", "")
    monkeypatch.setattr(settings, "APP_BASE_URL", "http://127.0.0.1:3001")


@pytest.mark.asyncio
async def test_email_status_reports_configured_providers(client, sample_tenant, google_configured):
    res = await client.get("/api/emails/status", headers={"X-Tenant-ID": sample_tenant.id})
    assert res.json() == {"providers": {"gmail": True, "outlook": False}, "connected": None}


@pytest.mark.asyncio
async def test_oauth_start_redirects_to_google(client, sample_tenant, google_configured):
    res = await client.get("/api/emails/oauth/gmail/start", headers={"X-Tenant-ID": sample_tenant.id})
    assert res.status_code == 307
    url = urlparse(res.headers["location"])
    q = parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert q["client_id"] == ["gid.apps.googleusercontent.com"]
    assert q["redirect_uri"] == ["http://127.0.0.1:3001/api/emails/oauth/gmail/callback"]
    assert "gmail.send" in q["scope"][0]
    assert q["access_type"] == ["offline"]
    assert q["state"][0]


@pytest.mark.asyncio
async def test_oauth_start_rejects_unconfigured_provider(client, sample_tenant, google_configured):
    res = await client.get("/api/emails/oauth/outlook/start", headers={"X-Tenant-ID": sample_tenant.id})
    assert res.status_code == 307
    assert res.headers["location"].startswith("/mailbox?error=")


@pytest.mark.asyncio
async def test_oauth_callback_connects_mailbox_and_records_consent(
    client, db_session, sample_tenant, google_configured, monkeypatch
):
    h = {"X-Tenant-ID": sample_tenant.id}

    async def fake_exchange(provider, code):
        assert (provider, code) == ("gmail", "the-code")
        return {"email": "ada@gmail.com", "access_token": "at", "refresh_token": "rt", "expires_in": 3600}

    monkeypatch.setattr("app.api.routers.emails.exchange_oauth_code", fake_exchange)
    start = await client.get("/api/emails/oauth/gmail/start", headers=h)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]

    for _ in range(2):  # reconnecting leaves exactly one active mailbox
        res = await client.get(f"/api/emails/oauth/gmail/callback?code=the-code&state={state}", headers=h)
        assert res.status_code == 307
        assert res.headers["location"] == "/mailbox?connected=gmail"

    active = (await db_session.execute(
        select(ConnectedEmail).where(ConnectedEmail.tenant_id == sample_tenant.id, ConnectedEmail.is_active.is_(True))
    )).scalars().all()
    assert [c.email_address for c in active] == ["ada@gmail.com"]
    consent = (await db_session.execute(
        select(Consent).where(Consent.tenant_id == sample_tenant.id, Consent.consent_type == "outreach_send")
    )).scalars().first()
    assert consent is not None

    status = await client.get("/api/emails/status", headers=h)
    assert status.json()["connected"] == {"email": "ada@gmail.com", "provider": "gmail"}


@pytest.mark.asyncio
async def test_oauth_callback_rejects_state_from_another_tenant(
    client, sample_tenant, second_tenant, google_configured
):
    start = await client.get("/api/emails/oauth/gmail/start", headers={"X-Tenant-ID": second_tenant.id})
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    res = await client.get(
        f"/api/emails/oauth/gmail/callback?code=c&state={state}", headers={"X-Tenant-ID": sample_tenant.id}
    )
    assert res.headers["location"].startswith("/mailbox?error=")


@pytest.mark.asyncio
async def test_run_scout_spreads_capped_matches_across_companies(db_session, sample_tenant, monkeypatch):
    monkeypatch.setattr("app.domain.scout.MAX_NEW_MATCHES_PER_RUN", 2)
    await roles_service.select_roles(db_session, sample_tenant.id, ["role_fullstack_eng"])
    fullstack = lambda i: {"id": i, "title": "Full Stack Engineer", "absolute_url": f"https://gh/acme/{i}",  # noqa: E731
                           "jobUrl": f"https://ashby/zeta/{i}", "location": "Remote", "content": "x" * 400}
    boards = {"greenhouse": {"jobs": [fullstack(1), fullstack(2)]}, "ashby": {"jobs": [fullstack(3)]}}
    transport = httpx.MockTransport(lambda r: httpx.Response(
        200, text=json.dumps(boards["greenhouse" if "greenhouse" in str(r.url) else "ashby"])
    ))
    async with httpx.AsyncClient(transport=transport) as c:
        await run_scout(db_session, sample_tenant.id, boards=BOARDS, client=c)
    companies = (await db_session.execute(
        select(JobListing.company).join(JobMatch, JobMatch.job_id == JobListing.id).where(JobMatch.tenant_id == sample_tenant.id)
    )).scalars().all()
    assert sorted(companies) == ["Acme", "Zeta"]


@pytest.mark.asyncio
async def test_run_scout_scores_new_matches_against_the_jd(db_session, sample_tenant):
    from app.domain.fit_service import get_fit

    await roles_service.select_roles(db_session, sample_tenant.id, ["role_fullstack_eng"])
    async with httpx.AsyncClient(transport=_boards_transport()) as c:
        await run_scout(db_session, sample_tenant.id, boards=BOARDS, client=c)
    match = (await db_session.execute(select(JobMatch).where(JobMatch.tenant_id == sample_tenant.id))).scalars().first()
    fit = await get_fit(db_session, sample_tenant.id, match.job_id)
    assert fit is not None and match.match_score == fit.score * 2
