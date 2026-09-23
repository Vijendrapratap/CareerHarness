"""Scout Agent: scheduling, rate limits (RD-03) and job discovery for the candidate's selected roles."""

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import outbox
from app.domain import sources
from app.domain.models import JobMatch, RoleSelection, ScoutSchedule, Tenant
from app.domain.roles import roles_service

# Public job boards scanned for every candidate (verified live). Add boards here.
DEFAULT_BOARDS: List[Dict[str, str]] = [
    *({"portal": "greenhouse", "org": o, "name": n} for o, n in (
        ("stripe", "Stripe"), ("airbnb", "Airbnb"), ("databricks", "Databricks"), ("cloudflare", "Cloudflare"),
        ("gitlab", "GitLab"), ("figma", "Figma"), ("discord", "Discord"), ("robinhood", "Robinhood"),
        ("coinbase", "Coinbase"), ("dropbox", "Dropbox"), ("twilio", "Twilio"), ("asana", "Asana"),
    )),
    {"portal": "lever", "org": "spotify", "name": "Spotify"},
    *({"portal": "ashby", "org": o, "name": n} for o, n in (
        ("openai", "OpenAI"), ("linear", "Linear"), ("notion", "Notion"), ("ramp", "Ramp"), ("supabase", "Supabase"),
    )),
]
MAX_WORKDAY_QUERIES = 2       # role titles searched on each Workday site
MAX_WORKDAY_DETAILS = 5       # full descriptions fetched per Workday employer
MAX_CONCURRENT_REQUESTS = 8
MAX_NEW_MATCHES_PER_RUN = 50
_SENIORITY = {"senior", "sr", "staff", "principal", "junior", "jr"}


class ScoutError(Exception):
    pass


class ScoutRateLimitError(ScoutError):
    """Raised when on-demand manual scan exceeds plan allowance (RD-03)."""
    pass


class ScoutSchedulerService:
    """Manages autonomous cron scheduling and rate-limited manual scan triggers."""

    @staticmethod
    async def auto_schedule_on_gate_pass(
        session: AsyncSession,
        tenant_id: str,
    ) -> ScoutSchedule:
        """Activates the Scout cadence (runs as soon as roles are selected; never gated on readiness)."""
        # Check tenant plan
        tenant = await session.get(Tenant, tenant_id)
        cadence = "hourly" if (tenant and tenant.plan == "pro") else "daily"

        sched_q = select(ScoutSchedule).where(ScoutSchedule.tenant_id == tenant_id)
        schedule = (await session.execute(sched_q)).scalar_one_or_none()

        if not schedule:
            schedule = ScoutSchedule(
                tenant_id=tenant_id,
                cadence=cadence,
                is_active=True,
            )
            session.add(schedule)
        else:
            schedule.cadence = cadence
            schedule.is_active = True

        # Emit scout.started event
        await outbox.record_event(
            session=session,
            tenant_id=tenant_id,
            event_name="scout.started",
            payload={"cadence": cadence, "trigger": "auto_gate_pass"},
        )
        await session.flush()
        return schedule

    @staticmethod
    async def trigger_manual_scan(
        session: AsyncSession,
        tenant_id: str,
    ) -> dict:
        """RD-03: Manual scan rate-limited to 3/day (Free) and 10/day (Pro)."""
        tenant = await session.get(Tenant, tenant_id)
        is_pro = (tenant and tenant.plan == "pro")
        daily_limit = 10 if is_pro else 3

        sched_q = select(ScoutSchedule).where(ScoutSchedule.tenant_id == tenant_id)
        schedule = (await session.execute(sched_q)).scalar_one_or_none()

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if not schedule:
            schedule = ScoutSchedule(
                tenant_id=tenant_id,
                cadence="hourly" if is_pro else "daily",
                manual_scans_today=0,
                last_manual_scan_date=today_str,
                is_active=True,
            )
            session.add(schedule)
            await session.flush()

        # Reset counter if new day
        if schedule.last_manual_scan_date != today_str:
            schedule.manual_scans_today = 0
            schedule.last_manual_scan_date = today_str

        # Enforce rate limit
        if schedule.manual_scans_today >= daily_limit:
            raise ScoutRateLimitError(
                f"RD-03: Manual scan limit reached ({daily_limit}/day on {'Pro' if is_pro else 'Free'} plan). "
                f"Upgrade to Pro for 10 scans/day or wait for tomorrow."
            )

        schedule.manual_scans_today += 1
        schedule.last_run_at = datetime.now(timezone.utc)

        # Emit scout.started event
        await outbox.record_event(
            session=session,
            tenant_id=tenant_id,
            event_name="scout.started",
            payload={
                "trigger": "manual_scan",
                "scans_used": schedule.manual_scans_today,
                "daily_limit": daily_limit,
            },
        )
        await session.flush()

        return {
            "status": "scout_started",
            "scans_used": schedule.manual_scans_today,
            "scans_remaining": daily_limit - schedule.manual_scans_today,
            "daily_limit": daily_limit,
        }


class AtsJobScraper:
    """Capability seam for discovering jobs from public ATS APIs (Greenhouse, Lever, Ashby)."""

    @staticmethod
    async def fetch_greenhouse_jobs(
        board_token: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Dict[str, Any]]:
        """Fetches public jobs from Greenhouse API (https://boards-api.greenhouse.io/v1/boards/{board}/jobs)."""
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0)
            should_close = True

        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
            jobs = []
            for j in data.get("jobs", []):
                jobs.append({
                    "title": j.get("title", "Software Engineer"),
                    "company": board_token.capitalize(),
                    "url": j.get("absolute_url", f"https://boards.greenhouse.io/{board_token}/jobs/{j.get('id')}"),
                    "location": j.get("location", {}).get("name", "Remote") if isinstance(j.get("location"), dict) else "Remote",
                    "description": j.get("content", "") or j.get("title", ""),
                    "portal_type": "greenhouse",
                    "posted_at": _iso(j.get("updated_at")),
                })
            return jobs
        except Exception:
            return []
        finally:
            if should_close:
                await client.aclose()

    @staticmethod
    async def fetch_lever_jobs(
        site: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Dict[str, Any]]:
        """Fetches public postings from Lever API (https://api.lever.co/v0/postings/{site})."""
        url = f"https://api.lever.co/v0/postings/{site}?mode=json"
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0)
            should_close = True

        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
            jobs = []
            for j in data if isinstance(data, list) else []:
                categories = j.get("categories", {})
                location = categories.get("location", "Remote") if isinstance(categories, dict) else "Remote"
                jobs.append({
                    "title": j.get("text", "Software Engineer"),
                    "company": site.capitalize(),
                    "url": j.get("hostedUrl", f"https://jobs.lever.co/{site}/{j.get('id')}"),
                    "location": location,
                    "description": j.get("descriptionPlain", "") or j.get("text", ""),
                    "portal_type": "lever",
                    "posted_at": _epoch_ms(j.get("createdAt")),
                })
            return jobs
        except Exception:
            return []
        finally:
            if should_close:
                await client.aclose()

    @staticmethod
    async def fetch_ashby_jobs(
        organization: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Dict[str, Any]]:
        """Fetches public jobs from Ashby API (https://api.ashbyhq.com/posting-api/job-board/{org})."""
        url = f"https://api.ashbyhq.com/posting-api/job-board/{organization}"
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0)
            should_close = True

        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
            jobs = []
            for j in data.get("jobs", []):
                jobs.append({
                    "title": j.get("title", "Software Engineer"),
                    "company": organization.capitalize(),
                    "url": j.get("jobUrl", f"https://jobs.ashbyhq.com/{organization}/{j.get('id')}"),
                    "location": j.get("location", "Remote"),
                    "description": j.get("descriptionPlain", "") or j.get("title", ""),
                    "portal_type": "ashby",
                    "posted_at": _iso(j.get("publishedAt")),
                })
            return jobs
        except Exception:
            return []
        finally:
            if should_close:
                await client.aclose()

    @staticmethod
    async def discover_and_ingest(
        session: AsyncSession,
        tenant_id: str,
        targets: List[Dict[str, str]],
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Any]:
        """Discovers jobs across specified target ATS portals and ingests them into the tenant's feed."""
        from app.domain.jobs import job_service

        ingested_jobs = []
        for target in targets:
            portal = target.get("portal", "greenhouse").lower()
            org = target.get("org", "")
            if not org:
                continue

            discovered: List[Dict[str, Any]] = []
            if portal == "greenhouse":
                discovered = await AtsJobScraper.fetch_greenhouse_jobs(org, client=client)
            elif portal == "lever":
                discovered = await AtsJobScraper.fetch_lever_jobs(org, client=client)
            elif portal == "ashby":
                discovered = await AtsJobScraper.fetch_ashby_jobs(org, client=client)

            for job_data in discovered:
                job_rec = await job_service.ingest_job(
                    session=session,
                    title=job_data["title"],
                    company=job_data["company"],
                    url=job_data["url"],
                    description=job_data["description"],
                    portal_type=job_data["portal_type"],
                    location=job_data.get("location", "Remote"),
                )
                match = await job_service.score_and_match_job(
                    session=session,
                    tenant_id=tenant_id,
                    job_id=job_rec.id,
                )
                ingested_jobs.append(job_rec)

        if ingested_jobs:
            await outbox.record_event(
                session=session,
                tenant_id=tenant_id,
                event_name="jobs.found",
                payload={"count": len(ingested_jobs)},
            )

        return ingested_jobs


scout_scheduler = ScoutSchedulerService()
ats_scraper = AtsJobScraper()


def _iso(value: Any) -> Optional[datetime]:
    return sources._iso(value)


def _epoch_ms(value: Any) -> Optional[datetime]:
    return sources._epoch(int(value) // 1000) if value else None


def _words(text: str) -> Set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _role_phrases(role: RoleSelection) -> List[Set[str]]:
    """Word sets that identify a role in a job title: its title plus catalog aliases.

    Seniority words are ignored; one-word aliases (e.g. "pm") are too broad and skipped.
    """
    role_def = roles_service.find_role_in_catalog(role.role_id)
    phrases = [_words(role.title) - _SENIORITY]
    for alias in (role_def or {}).get("aliases", []):
        words = _words(alias) - _SENIORITY
        if len(words) >= 2:
            phrases.append(words)
    return [p for p in phrases if p]


async def run_scout(
    session: AsyncSession,
    tenant_id: str,
    boards: Optional[List[Dict[str, str]]] = None,
    client: Optional[httpx.AsyncClient] = None,
    open_sources: bool = True,
) -> Dict[str, int]:
    """Finds new postings for the candidate's roles across every source, scores them, stores matches.

    Pipeline: fetch all sources concurrently -> keep fresh postings in the candidate's work mode and
    locations -> drop duplicates (across sources and already-matched jobs) -> match titles to roles ->
    interleave companies under the per-run cap -> fetch Workday details for the chosen few -> store.
    All network I/O finishes before the first write so SQLite is never locked during a fetch.
    """
    from app.domain.candidate_facts import get_facts, update_facts
    from app.domain.jobs import job_service
    from app.domain.models import JobListing

    roles = sorted(await roles_service.get_selected_roles(session, tenant_id), key=lambda r: r.rank)
    if not roles:
        return {"sources": 0, "boards_scanned": 0, "new_matches": 0}
    facts = await get_facts(session, tenant_id)
    boards = list(DEFAULT_BOARDS if boards is None else boards)
    queries = list(dict.fromkeys(r.title for r in roles))[:3]
    role_phrases = [(r, _role_phrases(r)) for r in roles]
    seen_keys = {
        sources.dedupe_key({"company": c, "title": t})
        for c, t in (await session.execute(
            select(JobListing.company, JobListing.title)
            .join(JobMatch, JobMatch.job_id == JobListing.id)
            .where(JobMatch.tenant_id == tenant_id)
        )).all()
    }

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    limiter = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def limited(coro):
        async with limiter:
            try:
                return await coro
            except Exception:  # one broken source must not sink the scan
                return []

    try:
        # Boards of companies the candidate named: discover once, then cache in their facts.
        known_boards: Dict[str, Optional[str]] = dict(facts.get("company_boards") or {})
        wanted = [c for c in facts.get("target_companies") or [] if c not in known_boards]
        if wanted:
            known_boards.update(await sources.discover_boards(client, wanted))
        for company, board in known_boards.items():
            if board and company in (facts.get("target_companies") or []):
                portal, org = board.split(":", 1)
                boards.append({"portal": portal, "org": org, "name": company})

        ats = {"greenhouse": AtsJobScraper.fetch_greenhouse_jobs, "lever": AtsJobScraper.fetch_lever_jobs,
               "ashby": AtsJobScraper.fetch_ashby_jobs}
        tasks, labels = [], []
        for b in boards:
            if b["portal"] in ats:
                tasks.append(limited(ats[b["portal"]](b["org"], client=client)))
                labels.append(b.get("name"))
        if open_sources:
            opens = [sources.remoteok(client), sources.arbeitnow(client), sources.hn_who_is_hiring(client)]
            for q in queries:
                opens += [sources.remotive(client, q), sources.himalayas(client, q)]
            for employer in sources.WORKDAY_EMPLOYERS:
                opens += [sources.workday(client, employer, q) for q in queries[:MAX_WORKDAY_QUERIES]]
            tasks += [limited(c) for c in opens]
            labels += [None] * len(opens)
        results = await asyncio.gather(*tasks)

        # Filter, de-duplicate, match roles, interleave companies.
        now = datetime.now(timezone.utc)
        candidates = []
        per_company: Dict[str, int] = {}
        for label, postings in zip(labels, results, strict=True):
            for posting in postings:
                if label:
                    posting["company"] = label
                if not sources.is_fresh(posting, now) or not sources.passes_location(posting, facts):
                    continue
                key = sources.dedupe_key(posting)
                if key in seen_keys:
                    continue
                title_words = _words(posting["title"])
                role = next((r for r, phrases in role_phrases if any(p <= title_words for p in phrases)), None)
                if not role:
                    continue
                seen_keys.add(key)
                nth = per_company.get(posting["company"], 0)
                per_company[posting["company"]] = nth + 1
                candidates.append((nth, role, posting))
        candidates.sort(key=lambda c: (c[0], c[1].rank))
        chosen = candidates[:MAX_NEW_MATCHES_PER_RUN]

        # Workday search results have no description: fetch it only for the postings we keep.
        employers = {e["name"]: e for e in sources.WORKDAY_EMPLOYERS}
        detail_budget: Dict[str, int] = {}
        detail_jobs = []
        for i, (_, _, posting) in enumerate(chosen):
            employer = employers.get(posting["company"])
            if posting["portal_type"] == "workday" and employer:
                used = detail_budget.get(employer["name"], 0)
                if used < MAX_WORKDAY_DETAILS:
                    detail_budget[employer["name"]] = used + 1
                    detail_jobs.append((i, limited(sources.workday_detail(client, employer, posting))))
        for (i, _), detailed in zip(detail_jobs, await asyncio.gather(*(c for _, c in detail_jobs)), strict=True):
            if detailed:
                nth, role, _ = chosen[i]
                chosen[i] = (nth, role, detailed)
    finally:
        if owns_client:
            await client.aclose()

    # --- writes start here ---
    if known_boards != (facts.get("company_boards") or {}):
        await update_facts(session, tenant_id, {"company_boards": known_boards})
    matched_job_ids = set(
        (await session.execute(select(JobMatch.job_id).where(JobMatch.tenant_id == tenant_id))).scalars().all()
    )
    new_job_ids: List[str] = []
    for _, role, posting in chosen:
        job = await job_service.ingest_job(
            session=session,
            title=posting["title"],
            company=posting["company"],
            url=posting["url"],
            description=posting["description"],
            portal_type=posting["portal_type"],
            location=posting.get("location") or "Remote",
        )
        if job.id in matched_job_ids:
            continue
        matched_job_ids.add(job.id)
        new_job_ids.append(job.id)
        session.add(JobMatch(
            tenant_id=tenant_id,
            job_id=job.id,
            match_score=9.0 if role.rank == 1 else 8.0,
            why_matched=f"Title matches your target role '{role.title}'.",
            status="new",
        ))

    if new_job_ids:
        from app.domain.fit_service import evaluate_tenant

        await session.flush()
        await evaluate_tenant(session, tenant_id, new_job_ids)  # real JD fit replaces the title-only score
        await outbox.record_event(
            session=session, tenant_id=tenant_id, event_name="jobs.found", payload={"count": len(new_job_ids)}
        )
    await session.flush()
    return {"sources": len(tasks), "boards_scanned": len(boards), "new_matches": len(new_job_ids)}


# One scan per candidate at a time: overlapping scans race on the same rows (and SQLite allows one writer).
# ponytail: process-local lock; use a Redis lock if scans move to several worker processes.
_SCAN_LOCKS: Dict[str, asyncio.Lock] = {}


async def _scan_once(tenant_id: str) -> None:
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        await scout_scheduler.auto_schedule_on_gate_pass(session, tenant_id)
        await session.commit()  # release the write lock before the slow board fetch
        await run_scout(session, tenant_id)
        await session.commit()


async def scan_in_background(tenant_id: str) -> None:
    """Scan for one candidate after the request that asked for it has returned; waits for a running scan."""
    async with _SCAN_LOCKS.setdefault(tenant_id, asyncio.Lock()):
        await _scan_once(tenant_id)


async def start_scout_in_background(tenant_id: str) -> None:
    """Activates the Scout schedule and runs a first scan (roles were just chosen)."""
    await scan_in_background(tenant_id)
