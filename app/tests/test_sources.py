"""Open job sources: each fetcher normalizes its payload; filters and dedupe behave."""

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.domain import sources
from app.domain.sources import (
    arbeitnow,
    dedupe_key,
    discover_boards,
    fetch_json,
    himalayas,
    hn_who_is_hiring,
    is_fresh,
    passes_location,
    remoteok,
    remotive,
    workday,
)

NOW = datetime(2026, 9, 23, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def _instant(_seconds):
        return None

    monkeypatch.setattr(sources.asyncio, "sleep", _instant)


def client_for(routes):
    """routes: list of (substring, response-json | callable)."""

    def handler(request: httpx.Request) -> httpx.Response:
        for needle, body in routes:
            if needle in str(request.url):
                body = body(request) if callable(body) else body
                if isinstance(body, httpx.Response):
                    return body
                return httpx.Response(200, text=json.dumps(body))
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_remoteok_skips_legal_notice_and_normalizes():
    payload = [{"legal": "notice"}, {"position": "Backend Engineer", "company": "Acme", "location": "",
                                     "date": "2026-09-21T16:00:11+00:00", "url": "https://remoteok.com/1",
                                     "description": "<p>Python</p>"}]
    async with client_for([("remoteok.com/api", payload)]) as c:
        [job] = await remoteok(c)
    assert job["title"] == "Backend Engineer" and job["company"] == "Acme"
    assert job["location"] == "Remote" and job["portal_type"] == "remoteok"
    assert job["posted_at"] == datetime(2026, 9, 21, 16, 0, 11, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_remotive_and_himalayas_and_arbeitnow():
    routes = [
        ("remotive.com", {"jobs": [{"title": "Full Stack Dev", "company_name": "Kobo", "candidate_required_location": "USA",
                                    "publication_date": "2026-09-18T16:43:22", "url": "https://remotive.com/2",
                                    "description": "x"}]}),
        ("himalayas.app", {"jobs": [{"title": "Backend Security Engineer", "companyName": "micro1",
                                     "locationRestrictions": ["United States", "Canada"], "pubDate": 1790117005,
                                     "applicationLink": "https://himalayas.app/3", "description": "y"}]}),
        ("arbeitnow.com", {"data": [{"title": "Data Engineer", "company_name": "Maomao", "location": "Berlin",
                                     "remote": False, "created_at": 1790112625, "url": "https://arbeitnow.com/4",
                                     "description": "z"}]}),
    ]
    async with client_for(routes) as c:
        [a] = await remotive(c, "full stack")
        [b] = await himalayas(c, "backend")
        [d] = await arbeitnow(c)
    assert a["location"] == "Remote (USA)" and a["posted_at"].tzinfo is not None
    assert b["location"] == "Remote (United States, Canada)" and b["url"] == "https://himalayas.app/3"
    assert d["location"] == "Berlin" and d["posted_at"] == datetime.fromtimestamp(1790112625, tz=timezone.utc)


@pytest.mark.asyncio
async def test_hn_who_is_hiring_parses_first_line():
    routes = [
        ("search_by_date", {"hits": [{"objectID": "99", "title": "Ask HN: Who wants to be hired? (September 2026)"},
                                     {"objectID": "100", "title": "Ask HN: Who is hiring? (September 2026)"}]}),
        ("items/100", {"children": [
            {"id": 7, "created_at": "2026-09-02T10:00:00Z",
             "text": "Acme Robotics | Senior Backend Engineer | Remote (US) | Full-time<p>We use Python and Postgres."},
            {"id": 8, "created_at": "2026-09-02T11:00:00Z", "text": None},
            {"id": 9, "created_at": "2026-09-02T12:00:00Z",
             "text": "Snout (https://snout.example) | Staff Engineer | Hybrid NYC"},
        ]}),
    ]
    async with client_for(routes) as c:
        job, snout = await hn_who_is_hiring(c)
    assert snout["company"] == "Snout" and snout["location"] == "Hybrid NYC"
    assert job["company"] == "Acme Robotics" and job["title"] == "Senior Backend Engineer"
    assert job["location"] == "Remote (US)" and job["url"] == "https://news.ycombinator.com/item?id=7"
    assert "Python" in job["description"]


@pytest.mark.asyncio
async def test_workday_search_and_detail():
    employer = {"name": "NVIDIA", "tenant": "nvidia", "wd": "wd5", "site": "NVIDIAExternalCareerSite"}
    routes = [
        ("/jobs", {"total": 1, "jobPostings": [{"title": "Software Engineer", "locationsText": "Santa Clara, CA",
                                                "postedOn": "Posted 30+ Days Ago", "externalPath": "/job/SC/SE_JR1"}]}),
        ("/job/SC/SE_JR1", {"jobPostingInfo": {"jobDescription": "<p>C++ and CUDA</p>", "startDate": "2026-09-01",
                                                "externalUrl": "https://nvidia.wd5.myworkdayjobs.com/x/job/SC/SE_JR1"}}),
    ]
    async with client_for(routes) as c:
        [job] = await workday(c, employer, "software engineer")
        assert job["company"] == "NVIDIA" and job["posted_at"] <= NOW - timedelta(days=0)
        detailed = await sources.workday_detail(c, employer, job)
    assert detailed["description"] == "<p>C++ and CUDA</p>"
    assert detailed["posted_at"] == datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert detailed["url"].startswith("https://nvidia.wd5")


@pytest.mark.asyncio
async def test_fetch_json_retries_after_429():
    calls = {"n": 0}

    def flaky(_req):
        calls["n"] += 1
        return httpx.Response(429) if calls["n"] == 1 else httpx.Response(200, text='{"ok": 1}')

    async with client_for([("example.com", flaky)]) as c:
        assert await fetch_json(c, "GET", "https://example.com/x") == {"ok": 1}
    assert calls["n"] == 2


def test_freshness_location_and_dedupe():
    old = {"posted_at": NOW - timedelta(days=45)}
    assert not is_fresh(old, NOW) and is_fresh({"posted_at": None}, NOW) and is_fresh({"posted_at": NOW}, NOW)

    remote = {"location": "Remote (US)", "description": ""}
    onsite = {"location": "Berlin", "description": "Office in Berlin"}
    assert passes_location(remote, {"work_mode": "remote_only"})
    assert not passes_location(onsite, {"work_mode": "remote_only"})
    assert passes_location(onsite, {"work_mode": "hybrid", "locations": ["berlin"]})
    assert not passes_location(onsite, {"work_mode": "hybrid", "locations": ["London"]})
    assert passes_location(onsite, {})  # no preference given: keep everything

    assert dedupe_key({"company": "Acme, Inc.", "title": "Sr. Backend Engineer"}) == dedupe_key(
        {"company": "acme inc", "title": "SR Backend engineer "})


@pytest.mark.asyncio
async def test_discover_boards_probes_ats_slugs():
    routes = [
        ("boards-api.greenhouse.io/v1/boards/acmelabs/", {"jobs": []}),
        ("api.lever.co/v0/postings/zeta-corp", [{"id": 1}]),
    ]
    async with client_for(routes) as c:
        found = await discover_boards(c, ["Acme Labs", "Zeta Corp", "Nobody Co"])
    assert found == {"Acme Labs": "greenhouse:acmelabs", "Zeta Corp": "lever:zeta-corp", "Nobody Co": None}
