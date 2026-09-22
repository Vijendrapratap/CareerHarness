"""Role Catalog and Selection Service (F2, ON-01, ON-02)."""

from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import outbox
from app.domain.models import RoleSelection


class RoleSelectionError(Exception):
    """Raised when role selection violates quota or leadership constraints."""
    pass


# Canonical default roles catalog
DEFAULT_ROLE_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "role_fullstack_eng",
        "title": "Full Stack Engineer",
        "family": "Engineering",
        "aliases": ["full stack developer", "software engineer", "fullstack developer"],
        "baseline_skills": ["Python", "JavaScript", "SQL", "Git", "REST APIs", "Docker"],
        "is_leadership": False,
    },
    {
        "id": "role_backend_arch",
        "title": "Backend Architect",
        "family": "Engineering",
        "aliases": ["systems architect", "staff backend engineer", "principal engineer"],
        "baseline_skills": ["Distributed Systems", "SQL", "Database Design", "API Design", "Performance"],
        "is_leadership": False,
    },
    {
        "id": "role_frontend_spec",
        "title": "Senior Frontend Specialist",
        "family": "Engineering",
        "aliases": ["frontend engineer", "ui engineer", "web developer"],
        "baseline_skills": ["TypeScript", "React", "Next.js", "CSS", "Performance Profiling"],
        "is_leadership": False,
    },
    {
        "id": "role_eng_manager",
        "title": "Engineering Manager",
        "family": "Management",
        "aliases": ["tech lead manager", "engineering manager", "director of engineering"],
        "baseline_skills": ["People Leadership", "Roadmap Planning", "Hiring", "Mentorship", "Budgeting"],
        "is_leadership": True,
    },
    {
        "id": "role_product_mgr",
        "title": "Senior Product Manager",
        "family": "Product",
        "aliases": ["pm", "group product manager", "product lead"],
        "baseline_skills": ["Product Strategy", "User Research", "Agile", "Analytics", "Stakeholder Management"],
        "is_leadership": True,
    },
    {
        "id": "role_ai_engineer",
        "title": "AI Engineer",
        "family": "Data",
        "aliases": ["ai engineer", "applied ai", "llm engineer"],
        "baseline_skills": ["Python", "PyTorch", "LLMs", "Evaluation"],
        "is_leadership": False,
    },
    {
        "id": "role_ml_engineer",
        "title": "Machine Learning Engineer",
        "family": "Data",
        "aliases": ["machine learning engineer", "data science", "ml engineer"],
        "baseline_skills": ["Python", "PyTorch", "Machine Learning", "Feature Stores"],
        "is_leadership": False,
    },
    {
        "id": "role_data_engineer",
        "title": "Data Engineer",
        "family": "Data",
        "aliases": ["data engineer", "analytics engineer"],
        "baseline_skills": ["SQL", "Spark", "Pipelines", "Warehousing"],
        "is_leadership": False,
    },
    {
        "id": "role_data_lead",
        "title": "Data Science Manager",
        "family": "Data",
        "aliases": ["head of data", "data science manager"],
        "baseline_skills": ["People Leadership", "Roadmap Planning", "ML Strategy"],
        "is_leadership": True,
    },
]


class RoleService:
    """Manages role catalog lookups and candidate role selections."""

    @staticmethod
    def get_catalog() -> List[Dict[str, Any]]:
        return DEFAULT_ROLE_CATALOG

    @staticmethod
    def find_role_in_catalog(role_id: str) -> Optional[Dict[str, Any]]:
        for r in DEFAULT_ROLE_CATALOG:
            if r["id"] == role_id:
                return r
        return None

    @staticmethod
    async def select_roles(
        session: AsyncSession,
        tenant_id: str,
        role_ids: List[str],
        mgmt_experience: bool = False,
        priority_role_id: Optional[str] = None,
    ) -> List[RoleSelection]:
        """Sets candidate target roles, enforcing slot caps and priority role ranking (ON-01, ON-02)."""
        unique_roles = list(dict.fromkeys(role_ids))
        max_allowed = 4 if mgmt_experience else 3

        # ON-01: 4th slot locked without mgmt flag
        if len(unique_roles) > max_allowed:
            if not mgmt_experience and len(unique_roles) == 4:
                raise RoleSelectionError(
                    "Selecting a 4th role requires people or program management experience. "
                    "Check the management experience option to unlock the 4th slot."
                )
            raise RoleSelectionError(
                f"Maximum {max_allowed} roles allowed (attempted {len(unique_roles)})."
            )

        # Priority role defaults to first selected role if not specified
        target_priority = priority_role_id if priority_role_id in unique_roles else unique_roles[0]

        # Purge existing selections for this tenant
        await session.execute(delete(RoleSelection).where(RoleSelection.tenant_id == tenant_id))

        new_selections: List[RoleSelection] = []
        for idx, r_id in enumerate(unique_roles):
            role_def = RoleService.find_role_in_catalog(r_id)
            title = role_def["title"] if role_def else r_id
            # Priority role gets rank 1 (weights Scout ×1.5)
            rank = 1 if r_id == target_priority else (idx + 2)

            selection = RoleSelection(
                tenant_id=tenant_id,
                role_id=r_id,
                title=title,
                rank=rank,
                mgmt_lens=mgmt_experience,
            )
            session.add(selection)
            new_selections.append(selection)

        # Emit roles.selected event to outbox
        await outbox.record_event(
            session=session,
            tenant_id=tenant_id,
            event_name="roles.selected",
            payload={
                "roles": [s.title for s in new_selections],
                "priority_role_id": target_priority,
                "mgmt_lens": mgmt_experience,
            },
        )
        await session.flush()
        return new_selections

    @staticmethod
    async def get_selected_roles(
        session: AsyncSession,
        tenant_id: str,
    ) -> List[RoleSelection]:
        """Returns candidate selected roles ordered by priority rank (ON-02)."""
        query = (
            select(RoleSelection)
            .where(RoleSelection.tenant_id == tenant_id)
            .order_by(RoleSelection.rank.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def suggest_roles(background: str, mgmt_experience: bool = False) -> List[Dict[str, Any]]:
        """Offers up to three roles that match the candidate's background.

        Management experience unlocks one extra leadership role in the same family.
        """
        text = background.lower()
        catalog = RoleService.get_catalog()
        ic_roles = [role for role in catalog if not role["is_leadership"]]

        def score(role: Dict[str, Any]) -> int:
            total = 0
            alias_text = " ".join(role.get("aliases", [])).lower()
            phrases = [role["title"], role["family"], *role.get("aliases", []), *role.get("baseline_skills", [])]
            for phrase in phrases:
                token = phrase.lower().strip()
                if len(token) < 4 or token not in text:
                    continue
                total += 3 if token in role["title"].lower() or token in alias_text else 1
            return total

        positive = [role for role in ic_roles if score(role) > 0]
        positive.sort(key=score, reverse=True)
        if not positive:
            picked = [role for role in ic_roles if role["family"] == "Engineering"][:3]
        else:
            picked = positive[:3]
            family = picked[0]["family"]
            if len(picked) < 3:
                for role in ic_roles:
                    if role["family"] == family and role not in picked:
                        picked.append(role)
                    if len(picked) == 3:
                        break

        if mgmt_experience and picked:
            family = picked[0]["family"]
            lead = next(
                (role for role in catalog if role["is_leadership"] and role["family"] == family),
                None,
            )
            if lead is not None:
                picked.append(lead)
        return picked


roles_service = RoleService()
