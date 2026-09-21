"""Scout Agent Scheduling & Rate-Limiting Service (F7, RD-02, RD-03)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import outbox
from app.domain.models import ScoutSchedule, Tenant
from app.domain.readiness import readiness_gate


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
        """RD-02: Passing readiness score auto-schedules Scout cadence."""
        # Verify gate clearance
        await readiness_gate.verify_can_schedule_scout(session, tenant_id)

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
        await readiness_gate.verify_can_schedule_scout(session, tenant_id)

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
