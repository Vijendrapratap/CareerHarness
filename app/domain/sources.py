"""Open job sources beyond company ATS boards, plus freshness/location/duplicate filters.

Every fetcher returns normalized postings:
    {"title", "company", "url", "location", "description", "portal_type", "posted_at"}
where posted_at is an aware UTC datetime or None. Only open, no-login APIs are used.
"""

import asyncio
import html
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

USER_AGENT = "CareerHarness/1.0 (+job scout)"
MAX_AGE_DAYS = 30
_RETRY_STATUSES = {429, 500, 502, 503, 504}

# Public Workday career sites (CXS JSON API), verified live 2026-09-23.
WORKDAY_EMPLOYERS: List[Dict[str, str]] = [
    {"name": "NVIDIA", "tenant": "nvidia", "wd": "wd5", "site": "NVIDIAExternalCareerSite"},
    {"name": "Salesforce", "tenant": "salesforce", "wd": "wd12", "site": "External_Career_Site"},
    {"name": "Adobe", "tenant": "adobe", "wd": "wd5", "site": "external_experienced"},
    {"name": "Intel", "tenant": "intel", "wd": "wd1", "site": "External"},
    {"name": "Workday", "tenant": "workday", "wd": "wd5", "site": "Workday"},
    {"name": "Mastercard", "tenant": "mastercard", "wd": "wd1", "site": "CorporateCareers"},
    {"name": "PayPal", "tenant": "paypal", "wd": "wd1", "site": "jobs"},
    {"name": "HP", "tenant": "hp", "wd": "wd5", "site": "ExternalCareerSite"},
    {"name": "Target", "tenant": "target", "wd": "wd5", "site": "targetcareers"},
    {"name": "Capital One", "tenant": "capitalone", "wd": "wd12", "site": "Capital_One"},
    {"name": "Disney", "tenant": "disney", "wd": "wd5", "site": "disneycareer"},
    {"name": "Autodesk", "tenant": "autodesk", "wd": "wd1", "site": "Ext"},
    {"name": "Snap", "tenant": "snapchat", "wd": "wd1", "site": "snap"},
    {"name": "CrowdStrike", "tenant": "crowdstrike", "wd": "wd5", "site": "crowdstrikecareers"},
    {"name": "Zoom", "tenant": "zoom", "wd": "wd5", "site": "Zoom"},
    {"name": "Motorola Solutions", "tenant": "motorolasolutions", "wd": "wd5", "site": "Careers"},
    {"name": "Red Hat", "tenant": "redhat", "wd": "wd5", "site": "jobs"},
]


async def fetch_json(client: httpx.AsyncClient, method: str, url: str, **kwargs: Any) -> Any:
    """JSON body, or None on failure. Retries rate limits and 5xx twice (1s, 2s backoff)."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json", **kwargs.pop("headers", {})}
    for attempt in range(3):
        try:
            res = await client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError:
            res = None
        if res is not None and res.status_code == 200:
            try:
                return res.json()
            except ValueError:
                return None
        if res is not None and res.status_code not in _RETRY_STATUSES:
            return None
        if attempt < 2:
            await asyncio.sleep(2**attempt)
    return None


def _iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _epoch(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _posting(title: str, company: str, url: str, location: str, description: str,
             portal: str, posted_at: Optional[datetime]) -> Dict[str, Any]:
    return {
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "url": (url or "").strip(),
        "location": (location or "").strip() or "Remote",
        "description": description or "",
        "portal_type": portal,
        "posted_at": posted_at,
    }


def _remote_label(places: List[str]) -> str:
    places = [p for p in places if p]
    return f"Remote ({', '.join(places)})" if places else "Remote"


async def remoteok(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    data = await fetch_json(client, "GET", "https://remoteok.com/api")
    rows = [r for r in (data or []) if isinstance(r, dict) and r.get("position")]
    return [
        _posting(r["position"], r.get("company", ""), r.get("url", ""), _remote_label([r.get("location", "")]),
                 r.get("description", ""), "remoteok", _iso(r.get("date")))
        for r in rows
    ]


async def remotive(client: httpx.AsyncClient, query: str) -> List[Dict[str, Any]]:
    data = await fetch_json(client, "GET", "https://remotive.com/api/remote-jobs", params={"search": query, "limit": 50})
    return [
        _posting(r.get("title", ""), r.get("company_name", ""), r.get("url", ""),
                 _remote_label([r.get("candidate_required_location", "")]), r.get("description", ""),
                 "remotive", _iso(r.get("publication_date")))
        for r in (data or {}).get("jobs", [])
    ]


async def himalayas(client: httpx.AsyncClient, query: str) -> List[Dict[str, Any]]:
    data = await fetch_json(client, "GET", "https://himalayas.app/jobs/api/search", params={"q": query, "limit": 50})
    return [
        _posting(r.get("title", ""), r.get("companyName", ""), r.get("applicationLink") or r.get("guid", ""),
                 _remote_label(r.get("locationRestrictions") or []), r.get("description") or r.get("excerpt", ""),
                 "himalayas", _epoch(r.get("pubDate")))
        for r in (data or {}).get("jobs", [])
    ]


async def arbeitnow(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    data = await fetch_json(client, "GET", "https://www.arbeitnow.com/api/job-board-api")
    return [
        _posting(r.get("title", ""), r.get("company_name", ""), r.get("url", ""),
                 _remote_label([r.get("location", "")]) if r.get("remote") else r.get("location", ""),
                 r.get("description", ""), "arbeitnow", _epoch(r.get("created_at")))
        for r in (data or {}).get("data", [])
    ]


_ROLE_WORDS = re.compile(r"engineer|developer|scientist|manager|designer|architect|analyst|lead|sre|devops|"
                         r"head of|director|product|researcher|consultant|specialist", re.I)
_PLACE_WORDS = re.compile(r"remote|onsite|on-site|hybrid|\b[A-Z][a-z]+,\s*[A-Z]{2}\b|london|berlin|new york|"
                          r"san francisco|nyc|sf\b|toronto|bangalore|bengaluru|singapore|amsterdam|paris|us\b|eu\b", re.I)


async def hn_who_is_hiring(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Top-level comments of the latest "Ask HN: Who is hiring?" thread (Company | Role | Location | ...)."""
    search = await fetch_json(client, "GET", "https://hn.algolia.com/api/v1/search_by_date",
                              params={"tags": "story,author_whoishiring", "hitsPerPage": 5})
    thread = next((h for h in (search or {}).get("hits", []) if "who is hiring" in h.get("title", "").lower()), None)
    if not thread:
        return []
    item = await fetch_json(client, "GET", f"https://hn.algolia.com/api/v1/items/{thread['objectID']}")
    postings = []
    for child in (item or {}).get("children", []):
        text = child.get("text") or ""
        first = html.unescape(re.split(r"<p>|\n", text, maxsplit=1)[0])
        parts = [re.sub(r"<[^>]+>", "", p).strip() for p in first.split("|")]
        if len(parts) < 2:
            continue
        role = next((p for p in parts[1:] if _ROLE_WORDS.search(p)), "")
        if not role:
            continue
        place = next((p for p in parts[1:] if p is not role and _PLACE_WORDS.search(p)), "")
        company = re.sub(r"\(?https?://\S+\)?", "", parts[0]).strip(" -–()")
        postings.append(_posting(role, company, f"https://news.ycombinator.com/item?id={child['id']}",
                                 place, text, "hn", _iso(child.get("created_at"))))
    return postings


def _workday_base(employer: Dict[str, str]) -> str:
    t = employer["tenant"]
    return f"https://{t}.{employer['wd']}.myworkdayjobs.com/wday/cxs/{t}/{employer['site']}"


def _workday_posted(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """'Posted Today' / 'Posted Yesterday' / 'Posted 4 Days Ago' / 'Posted 30+ Days Ago'."""
    now = now or datetime.now(timezone.utc)
    low = (text or "").lower()
    if "today" in low:
        return now
    if "yesterday" in low:
        return now - timedelta(days=1)
    m = re.search(r"(\d+)\+?\s*days?", low)
    return now - timedelta(days=int(m.group(1))) if m else None


async def workday(client: httpx.AsyncClient, employer: Dict[str, str], query: str, limit: int = 20) -> List[Dict[str, Any]]:
    body = {"appliedFacets": {}, "limit": limit, "offset": 0, "searchText": query}
    data = await fetch_json(client, "POST", f"{_workday_base(employer)}/jobs", json=body)
    host = f"https://{employer['tenant']}.{employer['wd']}.myworkdayjobs.com/{employer['site']}"
    return [
        {**_posting(p.get("title", ""), employer["name"], host + p.get("externalPath", ""),
                    p.get("locationsText", ""), "", "workday", _workday_posted(p.get("postedOn", ""))),
         "external_path": p.get("externalPath", "")}
        for p in (data or {}).get("jobPostings", [])
        if p.get("externalPath")
    ]


async def workday_detail(client: httpx.AsyncClient, employer: Dict[str, str], posting: Dict[str, Any]) -> Dict[str, Any]:
    """Adds the full description, real posting date and public URL (one request per posting)."""
    data = await fetch_json(client, "GET", _workday_base(employer) + posting["external_path"])
    info = (data or {}).get("jobPostingInfo") or {}
    start = info.get("startDate")
    return {
        **posting,
        "description": info.get("jobDescription") or posting["description"],
        "posted_at": _iso(f"{start}T00:00:00+00:00") if start else posting["posted_at"],
        "url": info.get("externalUrl") or posting["url"],
    }


# ---- Filters --------------------------------------------------------------------------------

_REMOTE = re.compile(r"\bremote\b|anywhere|work from home", re.I)


def is_fresh(posting: Dict[str, Any], now: datetime, max_age_days: int = MAX_AGE_DAYS) -> bool:
    posted = posting.get("posted_at")
    return posted is None or now - posted <= timedelta(days=max_age_days)


def passes_location(posting: Dict[str, Any], facts: Dict[str, Any]) -> bool:
    """Pre-filter by the candidate's stated work mode/locations; with no preference, keep everything."""
    mode = facts.get("work_mode")
    wanted = [w.lower() for w in facts.get("locations") or [] if w.strip()]
    location = posting.get("location") or ""
    remote = bool(_REMOTE.search(location))
    if mode == "remote_only":
        return remote
    if wanted and mode != "any":
        return remote or any(w in location.lower() for w in wanted)
    return True


def dedupe_key(posting: Dict[str, Any]) -> str:
    def norm(text: str) -> str:
        words = re.findall(r"[a-z0-9]+", (text or "").lower())
        return " ".join(w for w in words if w not in {"inc", "llc", "ltd", "gmbh", "sr", "senior"})
    return f"{norm(posting.get('company', ''))}|{norm(posting.get('title', ''))}"


# ---- Company board discovery ----------------------------------------------------------------

def _slugs(company: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", company.lower())
    return list(dict.fromkeys(["".join(words), "-".join(words)])) if words else []


async def _board_exists(client: httpx.AsyncClient, portal: str, slug: str) -> bool:
    urls = {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        "lever": f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=1",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
    }
    data = await fetch_json(client, "GET", urls[portal])
    return isinstance(data, list) or (isinstance(data, dict) and "jobs" in data)


async def discover_boards(client: httpx.AsyncClient, companies: List[str]) -> Dict[str, Optional[str]]:
    """Company name -> "portal:slug" for the first Greenhouse/Lever/Ashby board that exists, else None."""

    async def find(company: str) -> Optional[str]:
        for portal in ("greenhouse", "lever", "ashby"):
            for slug in _slugs(company):
                if await _board_exists(client, portal, slug):
                    return f"{portal}:{slug}"
        return None

    found = await asyncio.gather(*(find(c) for c in companies))
    return dict(zip(companies, found, strict=True))
