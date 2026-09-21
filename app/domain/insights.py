"""Insights & Settings Domain Module (F12).

Provides:
- Funnel metrics and conversion analytics across portals and versions (BT-01).
- Trusted Mode toggle with readiness score validation gate (BT-02).
- Settings management: cadence, email disconnect, and tenant profile (BT-03).
"""

from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    ApplicationTrack,
    ConnectedEmail,
    DocumentVersion,
    ReadinessScore,
    ScoutSchedule,
    Tenant,
    TodoItem,
)


class SettingsError(Exception):
    """Base exception for settings operations."""
    pass


class ReadinessGateNotMetError(SettingsError):
    """Raised when trying to enable Trusted Mode without clearing readiness gate (score >= 70, 0 criticals) (BT-02)."""
    pass


class PlanUpgradeRequiredError(SettingsError):
    """Raised when a Free plan user requests Pro-exclusive features (e.g. hourly scout scan)."""
    pass


# ============================================================================
# FUNNEL METRICS & CONVERSION ANALYTICS (BT-01)
# ============================================================================

async def get_funnel_analytics(
    session: AsyncSession,
    tenant_id: str,
) -> Dict[str, Any]:
    """Calculate aggregated funnel metrics and conversion rates for tenant (BT-01)."""
    # 1. Total applications
    stmt_apps = select(ApplicationTrack).where(ApplicationTrack.tenant_id == tenant_id)
    res_apps = await session.execute(stmt_apps)
    apps = list(res_apps.scalars().all())

    total_apps = len(apps)
    interviews = sum(1 for a in apps if a.status in ("interview", "offer"))
    assessments = sum(1 for a in apps if a.status == "assessment")
    rejections = sum(1 for a in apps if a.status == "rejected")
    offers = sum(1 for a in apps if a.status == "offer")
    ghosted = sum(1 for a in apps if a.status == "ghosted" or a.is_ghosted)

    response_count = interviews + assessments + rejections
    response_rate = round((response_count / total_apps * 100), 1) if total_apps > 0 else 0.0
    interview_rate = round((interviews / total_apps * 100), 1) if total_apps > 0 else 0.0
    offer_rate = round((offers / total_apps * 100), 1) if total_apps > 0 else 0.0
    ghost_rate = round((ghosted / total_apps * 100), 1) if total_apps > 0 else 0.0

    # 2. Group by portal type
    by_portal: Dict[str, Dict[str, int]] = {}
    for a in apps:
        portal = a.portal_type or "direct"
        if portal not in by_portal:
            by_portal[portal] = {"total": 0, "interviews": 0, "rejections": 0}
        by_portal[portal]["total"] += 1
        if a.status in ("interview", "offer"):
            by_portal[portal]["interviews"] += 1
        elif a.status == "rejected":
            by_portal[portal]["rejections"] += 1

    # 3. Group by resume version
    stmt_versions = select(DocumentVersion).where(
        DocumentVersion.tenant_id == tenant_id,
        DocumentVersion.document_type == "resume",
    )
    res_versions = await session.execute(stmt_versions)
    versions = list(res_versions.scalars().all())

    version_metrics: List[Dict[str, Any]] = []
    for v in versions:
        if v.applications_count > 0:
            rate = round((v.interviews_count / v.applications_count) * 100, 1)
        else:
            rate = 0.0
        version_metrics.append({
            "version_id": v.id,
            "version_number": v.version_number,
            "title": v.title,
            "is_master": v.is_master,
            "applications": v.applications_count,
            "interviews": v.interviews_count,
            "interview_rate": rate,
        })

    return {
        "funnel": {
            "total_applications": total_apps,
            "interviews": interviews,
            "assessments": assessments,
            "rejections": rejections,
            "offers": offers,
            "ghosted": ghosted,
            "response_rate_percent": response_rate,
            "interview_rate_percent": interview_rate,
            "offer_rate_percent": offer_rate,
            "ghost_rate_percent": ghost_rate,
        },
        "by_portal_type": by_portal,
        "by_resume_version": version_metrics,
    }


# ============================================================================
# SETTINGS & TRUSTED MODE MANAGEMENT (BT-02, BT-03)
# ============================================================================

async def toggle_trusted_mode(
    session: AsyncSession,
    tenant_id: str,
    enable: bool,
) -> Tenant:
    """Toggle Trusted Mode for candidate (BT-02).

    Gate check: Cannot enable Trusted Mode unless candidate has Front-Face score >= 70
    and 0 open critical todos.
    """
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    res = await session.execute(stmt)
    tenant = res.scalar_one_or_none()
    if not tenant:
        raise SettingsError(f"Tenant {tenant_id} not found")

    if enable:
        # Check readiness score
        score_stmt = (
            select(ReadinessScore)
            .where(ReadinessScore.tenant_id == tenant_id)
            .order_by(ReadinessScore.created_at.desc())
        )
        score_res = await session.execute(score_stmt)
        latest_score = score_res.scalars().first()

        if not latest_score or latest_score.overall_score < 70 or latest_score.is_capped_at_69:
            score_val = latest_score.overall_score if latest_score else 0
            raise ReadinessGateNotMetError(
                f"Cannot enable Trusted Mode: Readiness score is {score_val} (minimum 70 required)."
            )

        # Check for open critical todos
        todo_stmt = select(func.count(TodoItem.id)).where(
            TodoItem.tenant_id == tenant_id,
            TodoItem.severity == "critical",
            TodoItem.status == "open",
        )
        todo_res = await session.execute(todo_stmt)
        critical_count = todo_res.scalar() or 0

        if critical_count > 0:
            raise ReadinessGateNotMetError(
                f"Cannot enable Trusted Mode: {critical_count} critical front-face items remain open."
            )

    tenant.trusted_mode = enable
    await session.flush()
    return tenant


async def update_scout_cadence(
    session: AsyncSession,
    tenant_id: str,
    cadence: str,
) -> ScoutSchedule:
    """Update Scout scanning cadence ('daily' or 'hourly') (BT-03)."""
    # Check tenant plan
    tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
    tenant_res = await session.execute(tenant_stmt)
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        raise SettingsError(f"Tenant {tenant_id} not found")

    if cadence == "hourly" and tenant.plan != "pro":
        raise PlanUpgradeRequiredError("Hourly scout scanning requires Pro subscription.")

    sched_stmt = select(ScoutSchedule).where(ScoutSchedule.tenant_id == tenant_id)
    sched_res = await session.execute(sched_stmt)
    sched = sched_res.scalar_one_or_none()

    if not sched:
        sched = ScoutSchedule(tenant_id=tenant_id, cadence=cadence, is_active=True)
        session.add(sched)
    else:
        sched.cadence = cadence

    await session.flush()
    return sched


async def disconnect_mailbox(
    session: AsyncSession,
    tenant_id: str,
) -> bool:
    """Disconnect and revoke connected email account (BT-03)."""
    stmt = select(ConnectedEmail).where(ConnectedEmail.tenant_id == tenant_id)
    res = await session.execute(stmt)
    mailboxes = list(res.scalars().all())

    for mb in mailboxes:
        await session.delete(mb)

    await session.flush()
    return len(mailboxes) > 0


async def get_settings_summary(
    session: AsyncSession,
    tenant_id: str,
) -> Dict[str, Any]:
    """Retrieve complete settings summary for candidate dashboard."""
    tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
    tenant_res = await session.execute(tenant_stmt)
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        raise SettingsError(f"Tenant {tenant_id} not found")

    # Readiness score
    score_stmt = (
        select(ReadinessScore)
        .where(ReadinessScore.tenant_id == tenant_id)
        .order_by(ReadinessScore.created_at.desc())
    )
    score_res = await session.execute(score_stmt)
    score = score_res.scalars().first()

    # Scout schedule
    sched_stmt = select(ScoutSchedule).where(ScoutSchedule.tenant_id == tenant_id)
    sched_res = await session.execute(sched_stmt)
    sched = sched_res.scalar_one_or_none()

    # Mailbox
    mb_stmt = select(ConnectedEmail).where(ConnectedEmail.tenant_id == tenant_id)
    mb_res = await session.execute(mb_stmt)
    mb = mb_res.scalar_one_or_none()

    return {
        "tenant_id": tenant.id,
        "name": tenant.name,
        "plan": tenant.plan,
        "trusted_mode": tenant.trusted_mode,
        "readiness_score": score.overall_score if score else 0,
        "scout_cadence": sched.cadence if sched else "daily",
        "connected_email": mb.email_address if mb else None,
    }
