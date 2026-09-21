"""Scout Agent Scheduling & Rate-Limiting Service (F7, RD-02, RD-03)."""

from datetime import datetime, timezone

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


scout_scheduler = ScoutSchedulerService()
