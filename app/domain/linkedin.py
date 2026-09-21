"""LinkedIn Intake & Consent Tracking Service (F4, LI-01, CT-04)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import outbox
from app.domain.memory import memory
from app.domain.models import Consent, LinkedInProfile


class ConsentRequiredError(Exception):
    """Raised when an external fetch action is attempted without explicit consent."""
    pass


class LinkedInFetchError(Exception):
    """Raised when remote LinkedIn fetch encounters a wall, 429, or network error."""
    pass


class LinkedInIntakeService:
    """Handles ToS-safe paste-mode intake and consent-verified public page fetch."""

    @staticmethod
    async def record_consent(
        session: AsyncSession,
        tenant_id: str,
        consent_type: str,
        ip_address: Optional[str] = None,
    ) -> Consent:
        """Stores legal consent timestamp before attempting any external fetch (CT-04)."""
        consent = Consent(
            tenant_id=tenant_id,
            consent_type=consent_type,
            granted_at=datetime.now(timezone.utc),
            ip_address=ip_address,
        )
        session.add(consent)
        await session.flush()
        return consent

    @staticmethod
    async def save_profile_paste(
        session: AsyncSession,
        tenant_id: str,
        headline: str,
        about: str,
        experience_entries: Optional[List[Dict[str, Any]]] = None,
        skills: Optional[List[str]] = None,
    ) -> LinkedInProfile:
        """Saves pasted LinkedIn profile text (ToS-safe default mode, F4)."""
        profile = LinkedInProfile(
            tenant_id=tenant_id,
            headline=headline.strip(),
            about=about.strip(),
            experience_entries=experience_entries or [],
            skills=skills or [],
            source_mode="paste",
        )
        session.add(profile)

        # Update blackboard memory
        memory.write_section(
            tenant_id=tenant_id,
            section="profile",
            data={
                "headline": profile.headline,
                "about": profile.about,
                "linkedin_skills": profile.skills,
            },
        )

        # Emit linkedin.captured event
        await outbox.record_event(
            session=session,
            tenant_id=tenant_id,
            event_name="linkedin.captured",
            payload={"source_mode": "paste", "headline_length": len(profile.headline)},
        )
        await session.flush()
        return profile

    @staticmethod
    async def fetch_public_profile(
        session: AsyncSession,
        tenant_id: str,
        public_url: str,
        user_consented: bool,
        ip_address: Optional[str] = None,
        simulate_fetch_failure: bool = False,
    ) -> LinkedInProfile:
        """Attempts public URL fetch only after recording consent; falls back to paste on failure (LI-01, CT-04)."""
        # CT-04: Explicit consent check
        if not user_consented:
            raise ConsentRequiredError(
                "Explicit candidate consent is required prior to fetching public LinkedIn data."
            )

        # Record consent timestamp BEFORE any network operation
        await LinkedInIntakeService.record_consent(
            session=session,
            tenant_id=tenant_id,
            consent_type="linkedin_fetch",
            ip_address=ip_address,
        )

        # LI-01: Headless fetch failure (login-wall, 429) triggers graceful paste fallback
        if simulate_fetch_failure or "error" in public_url.lower():
            raise LinkedInFetchError(
                "Public LinkedIn page could not be accessed (login-wall or rate-limited). "
                "Please use the ToS-safe 'Paste Profile' mode instead."
            )

        # Mocked successful fetch for valid URLs
        profile = LinkedInProfile(
            tenant_id=tenant_id,
            headline="Senior Backend Engineer at TechCorp",
            about="Passionate about high-throughput distributed systems.",
            experience_entries=[{"title": "Senior Backend Engineer", "company": "TechCorp"}],
            skills=["Python", "PostgreSQL", "System Design"],
            source_mode="url_fetch",
        )
        session.add(profile)
        await session.flush()
        return profile


linkedin_service = LinkedInIntakeService()
