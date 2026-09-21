"""Capability Seams & Pluggable Provider Architecture.

Pattern borrowed from DeepSeek Harness (dsh):
Decouples Service Definitions (interfaces), Service Providers (implementations),
and Consumers (agents / tools), enabling swappable execution sandboxes and
multi-tier fallback ladders.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, TypeVar


@dataclass
class ProviderResult:
    success: bool
    channel: str
    tier: int
    data: Dict[str, Any]
    error_message: Optional[str] = None
    bot_blocked: bool = False


class AtsProvider(ABC):
    """Abstract capability provider for ATS portals."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'greenhouse', 'lever', 'email_apply')."""
        pass

    @property
    @abstractmethod
    def tier(self) -> int:
        """Mitigation tier (1=Stealth Bot, 2=Email Mailbox, 3=Candidate Handoff)."""
        pass

    @abstractmethod
    def matches(self, url: str) -> bool:
        """Returns True if this provider can handle the target application portal."""
        pass

    @abstractmethod
    async def submit(
        self,
        tenant_id: str,
        job_id: str,
        job_url: str,
        resume_version_id: str,
        payload: Dict[str, Any],
        simulate_bot_block: bool = False,
    ) -> ProviderResult:
        """Execute submission via this provider."""
        pass


T = TypeVar("T")


class CapabilitySeam(Generic[T]):
    """Registry seam decoupling service definitions from swappable providers."""

    def __init__(self, seam_name: str):
        self.seam_name = seam_name
        self._providers: Dict[str, T] = {}

    def register_provider(self, name: str, provider: T) -> None:
        self._providers[name] = provider

    def get_provider(self, name: str) -> Optional[T]:
        return self._providers.get(name)

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())


# ============================================================================
# CONCRETE ATS PROVIDERS (Tier 1, Tier 2, Tier 3)
# ============================================================================

class GreenhouseAtsProvider(AtsProvider):
    @property
    def name(self) -> str:
        return "greenhouse"

    @property
    def tier(self) -> int:
        return 1

    def matches(self, url: str) -> bool:
        return "greenhouse.io" in url.lower() or "gh_jid" in url.lower()

    async def submit(
        self,
        tenant_id: str,
        job_id: str,
        job_url: str,
        resume_version_id: str,
        payload: Dict[str, Any],
        simulate_bot_block: bool = False,
    ) -> ProviderResult:
        if simulate_bot_block:
            return ProviderResult(
                success=False,
                channel="ats_autofill",
                tier=1,
                bot_blocked=True,
                error_message="Cloudflare Turnstile challenge detected on Greenhouse portal",
                data={},
            )
        return ProviderResult(
            success=True,
            channel="ats_autofill",
            tier=1,
            data={"confirmation_code": f"GH-{job_id[:8].upper()}", "portal": "greenhouse"},
        )


class LeverAtsProvider(AtsProvider):
    @property
    def name(self) -> str:
        return "lever"

    @property
    def tier(self) -> int:
        return 1

    def matches(self, url: str) -> bool:
        return "lever.co" in url.lower()

    async def submit(
        self,
        tenant_id: str,
        job_id: str,
        job_url: str,
        resume_version_id: str,
        payload: Dict[str, Any],
        simulate_bot_block: bool = False,
    ) -> ProviderResult:
        if simulate_bot_block:
            return ProviderResult(
                success=False,
                channel="ats_autofill",
                tier=1,
                bot_blocked=True,
                error_message="CAPTCHA challenge detected on Lever portal",
                data={},
            )
        return ProviderResult(
            success=True,
            channel="ats_autofill",
            tier=1,
            data={"confirmation_code": f"LEV-{job_id[:8].upper()}", "portal": "lever"},
        )


class EmailApplyProvider(AtsProvider):
    @property
    def name(self) -> str:
        return "email_apply"

    @property
    def tier(self) -> int:
        return 2

    def matches(self, url: str) -> bool:
        return True  # Fallback provider

    async def submit(
        self,
        tenant_id: str,
        job_id: str,
        job_url: str,
        resume_version_id: str,
        payload: Dict[str, Any],
        simulate_bot_block: bool = False,
    ) -> ProviderResult:
        company_email = payload.get("company_email")
        if not company_email or not payload.get("has_connected_email"):
            return ProviderResult(
                success=False,
                channel="email_apply",
                tier=2,
                error_message="No connected mailbox or company application email found",
                data={},
            )
        return ProviderResult(
            success=True,
            channel="email_apply",
            tier=2,
            data={"confirmation_code": f"EMAIL-APPLY-{job_id[:8].upper()}", "recipient": company_email},
        )


class CandidateHandoffProvider(AtsProvider):
    @property
    def name(self) -> str:
        return "candidate_handoff"

    @property
    def tier(self) -> int:
        return 3

    def matches(self, url: str) -> bool:
        return True  # Universal terminal fallback

    async def submit(
        self,
        tenant_id: str,
        job_id: str,
        job_url: str,
        resume_version_id: str,
        payload: Dict[str, Any],
        simulate_bot_block: bool = False,
    ) -> ProviderResult:
        return ProviderResult(
            success=True,
            channel="candidate_handoff",
            tier=3,
            data={
                "confirmation_code": f"HANDOFF-{job_id[:8].upper()}",
                "bundle_url": f"/api/v1/handoff/{tenant_id}/{job_id}",
                "checklist_completed": True,
            },
        )


# ============================================================================
# ATS SEAM & FALLBACK LADDER COORDINATOR
# ============================================================================

class AtsSeam(CapabilitySeam[AtsProvider]):
    def __init__(self):
        super().__init__("ats_submitters")
        # Register standard providers
        self.register_provider("greenhouse", GreenhouseAtsProvider())
        self.register_provider("lever", LeverAtsProvider())
        self.register_provider("email_apply", EmailApplyProvider())
        self.register_provider("candidate_handoff", CandidateHandoffProvider())

    async def execute_with_fallback_ladder(
        self,
        tenant_id: str,
        job_id: str,
        job_url: str,
        resume_version_id: str,
        payload: Dict[str, Any],
        simulate_bot_block: bool = False,
    ) -> ProviderResult:
        """Executes application submission through the 3-tier fallback ladder."""
        # Determine Tier 1 provider based on URL match
        tier1_provider: Optional[AtsProvider] = None
        for p in self._providers.values():
            if p.tier == 1 and p.matches(job_url):
                tier1_provider = p
                break

        if not tier1_provider:
            # Default to greenhouse if unrecognized URL
            tier1_provider = self._providers["greenhouse"]

        # Step 1: Attempt Tier 1 (Playwright stealth automation)
        t1_res = await tier1_provider.submit(
            tenant_id=tenant_id,
            job_id=job_id,
            job_url=job_url,
            resume_version_id=resume_version_id,
            payload=payload,
            simulate_bot_block=simulate_bot_block,
        )
        if t1_res.success:
            return t1_res

        # Step 2: Attempt Tier 2 (Connected mailbox email apply)
        t2_provider = self._providers["email_apply"]
        t2_res = await t2_provider.submit(
            tenant_id=tenant_id,
            job_id=job_id,
            job_url=job_url,
            resume_version_id=resume_version_id,
            payload=payload,
        )
        if t2_res.success:
            return t2_res

        # Step 3: Terminal Fallback to Tier 3 (1-Click Candidate Handoff Bundle)
        t3_provider = self._providers["candidate_handoff"]
        return await t3_provider.submit(
            tenant_id=tenant_id,
            job_id=job_id,
            job_url=job_url,
            resume_version_id=resume_version_id,
            payload=payload,
        )


ats_seam = AtsSeam()
