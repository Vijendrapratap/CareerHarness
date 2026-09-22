"""OpenRouter agent roster.

Each agent is a DeepSeek model on the candidate's own OpenRouter key.
The handoff chain is the harness task-board order:
scout -> analyst -> tailor -> reviewer -> cover -> dispatcher.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from app.harness.registry import registry


@dataclass(frozen=True)
class AgentSpec:
    name: str
    provider: str
    tier: str
    tools: Tuple[str, ...]
    hands_off_to: Optional[str]
    system_prompt: str


_HONESTY = (
    "Use only facts already present in the candidate profile. "
    "Never invent companies, dates, metrics, or skills."
)

AGENT_ROSTER = {
    "counsellor": AgentSpec(
        name="counsellor",
        provider="openrouter",
        tier="mid",
        tools=("blackboard_read", "blackboard_write"),
        hands_off_to=None,
        system_prompt=f"You are the career counsellor. Ask the candidate eight onboarding questions. You may only store the candidate's words. {_HONESTY}",
    ),
    "profiler": AgentSpec(
        name="profiler",
        provider="openrouter",
        tier="mid",
        tools=("blackboard_read", "blackboard_write"),
        hands_off_to=None,
        system_prompt=f"You are the consulting profiler. Map target roles, resume, and LinkedIn gaps into a fix list. {_HONESTY}",
    ),
    "scout": AgentSpec(
        name="scout",
        provider="openrouter",
        tier="cheap",
        tools=("blackboard_read",),
        hands_off_to="analyst",
        system_prompt=f"You are the scout. Find roles that match the candidate's selected titles. {_HONESTY}",
    ),
    "analyst": AgentSpec(
        name="analyst",
        provider="openrouter",
        tier="mid",
        tools=("blackboard_read",),
        hands_off_to="tailor",
        system_prompt=f"You are the analyst. Score fit and flag likely ghost jobs before anyone applies. {_HONESTY}",
    ),
    "tailor": AgentSpec(
        name="tailor",
        provider="openrouter",
        tier="mid",
        tools=("blackboard_read", "blackboard_write"),
        hands_off_to="reviewer",
        system_prompt=(
            "You are the drafter. Rewrite the summary and reorder existing bullets for the target job. "
            "Return one JSON object with candidate_name, contact_info, summary, skills, experience, education. "
            f"{_HONESTY}"
        ),
    ),
    "reviewer": AgentSpec(
        name="reviewer",
        provider="openrouter",
        tier="frontier",
        tools=("blackboard_read",),
        hands_off_to="cover",
        system_prompt=(
            "You are the reviewer, a fresh pass over the draft. "
            "Reject any company, date, metric, or skill that is not in the master resume. "
            f"{_HONESTY}"
        ),
    ),
    "cover": AgentSpec(
        name="cover",
        provider="openrouter",
        tier="mid",
        tools=("blackboard_write",),
        hands_off_to="dispatcher",
        system_prompt=f"You are the cover-letter writer. Cite only achievements that survived review. {_HONESTY}",
    ),
    "dispatcher": AgentSpec(
        name="dispatcher",
        provider="openrouter",
        tier="cheap",
        tools=("ats_apply",),
        hands_off_to=None,
        system_prompt="You submit an approved packet. External submission stays behind the human gate unless trusted mode already covers it.",
    ),
}

HANDOFF_CHAIN = ("scout", "analyst", "tailor", "reviewer", "cover", "dispatcher")


def tool_schemas_for(names: Tuple[str, ...]) -> list:
    """OpenAI-style tool definitions for the names this agent is allowed to call."""
    schemas = []
    for name in names:
        tool = registry.get(name)
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.meta.name,
                    "description": tool.meta.description,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": True,
                    },
                },
            }
        )
    return schemas
