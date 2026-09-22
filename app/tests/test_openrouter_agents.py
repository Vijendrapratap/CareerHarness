"""OpenRouter agent roster, tool-calling loop, and drafter-reviewer handoff."""

import json
import uuid
from types import SimpleNamespace

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.keyvault import keyvault
from app.core.model_router import LLMResponse, ModelRouter, ToolCall, router
from app.domain.application_engine import draft_application_packet
from app.domain.models import Run
from app.domain.roles import roles_service
from app.harness.loop import agent_loop
from app.harness.roster import AGENT_ROSTER, HANDOFF_CHAIN
from app.harness.run import RunContext


def test_openrouter_roster_binds_deepseek_models_and_handoff_chain():
    """Each pipeline agent is pinned to OpenRouter, with the reviewer on the frontier model."""
    assert HANDOFF_CHAIN == (
        "scout",
        "analyst",
        "tailor",
        "reviewer",
        "cover",
        "dispatcher",
    )
    for name in HANDOFF_CHAIN:
        assert AGENT_ROSTER[name].provider == "openrouter"

    assert AGENT_ROSTER["tailor"].hands_off_to == "reviewer"
    assert AGENT_ROSTER["reviewer"].tier == "frontier"
    assert AGENT_ROSTER["dispatcher"].tools == ("ats_apply",)
    assert router.model_for("openrouter", AGENT_ROSTER["tailor"].tier) == "deepseek/deepseek-v4.1-flash"
    assert router.model_for("openrouter", AGENT_ROSTER["reviewer"].tier) == "deepseek/deepseek-r1"


@pytest.mark.asyncio
async def test_agent_roster_and_role_suggestion_are_public(db_session):
    """Settings can read the OpenRouter roster, and onboarding can ask for role options."""
    from app.api.deps import get_db
    from app.api.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        agents = await client.get("/api/runs/agents")
        suggested = await client.get(
            "/api/roles/suggest",
            params={"background": "data science pytorch spark", "mgmt_experience": True},
        )
    app.dependency_overrides.clear()

    assert agents.status_code == 200
    reviewer = next(item for item in agents.json() if item["name"] == "reviewer")
    assert reviewer["provider"] == "openrouter"
    assert reviewer["model"] == "deepseek/deepseek-r1"
    assert suggested.status_code == 200
    suggested_ids = [item["id"] for item in suggested.json()]
    assert len(suggested_ids) == 4
    assert "role_data_lead" in suggested_ids


def test_suggest_roles_offers_a_data_cluster_and_a_leadership_slot():
    """A data-science background gets at most three IC roles, plus one leadership role with management experience."""
    background = "data science, pytorch, spark pipelines"
    suggested = roles_service.suggest_roles(background, mgmt_experience=False)
    assert len(suggested) == 3
    assert {role["id"] for role in suggested} == {
        "role_ai_engineer",
        "role_ml_engineer",
        "role_data_engineer",
    }
    assert all(role["is_leadership"] is False for role in suggested)

    with_mgmt = roles_service.suggest_roles(background, mgmt_experience=True)
    assert len(with_mgmt) == 4
    assert with_mgmt[-1]["id"] == "role_data_lead"
    assert with_mgmt[-1]["is_leadership"] is True

    engineering = roles_service.suggest_roles("react next.js typescript frontend", mgmt_experience=False)
    engineering_ids = {role["id"] for role in engineering}
    assert "role_frontend_spec" in engineering_ids
    assert "role_ml_engineer" not in engineering_ids
    assert len(engineering) == 3


@pytest.mark.asyncio
async def test_model_router_sends_tools_and_parses_openrouter_tool_calls():
    """A live OpenRouter completion returns the tool the model selected, arguments parsed from JSON."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "blackboard_read",
                                        "arguments": '{"view_spec": ["profile"]}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        local = ModelRouter(http_client=client)
        response = await local.call(
            provider="openrouter",
            raw_key="sk-or-v1-live-example-key",
            tier="mid",
            system_prompt="You are the tailor.",
            messages=[{"role": "user", "content": "Read the profile."}],
            tools=[
                {
                    "type": "function",
                    "function": {"name": "blackboard_read", "description": "Read memory", "parameters": {}},
                }
            ],
        )

    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["body"]["model"] == "deepseek/deepseek-v4.1-flash"
    assert captured["body"]["tools"][0]["function"]["name"] == "blackboard_read"
    assert response.tool_calls == [
        ToolCall(id="call_1", name="blackboard_read", arguments={"view_spec": ["profile"]})
    ]


@pytest.mark.asyncio
async def test_loop_executes_the_openrouter_tool_call(db_session, sample_tenant, monkeypatch):
    """The tailor step runs the tool OpenRouter returned, limited to that agent's allowlist."""
    await keyvault.store_key(db_session, sample_tenant.id, "openrouter", "sk-or-v1-live-example-key")

    async def fake_call(**kwargs):
        assert kwargs["provider"] == "openrouter"
        assert kwargs["tier"] == "mid"
        names = [tool["function"]["name"] for tool in kwargs["tools"]]
        assert names == ["blackboard_read", "blackboard_write"]
        return LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_write",
                    name="blackboard_write",
                    arguments={"section": "resume_bullets", "data": ["Python"]},
                )
            ],
        )

    monkeypatch.setattr(router, "call", fake_call)

    db_run = Run(
        id=str(uuid.uuid4()),
        tenant_id=sample_tenant.id,
        agent_name="tailor",
        goal="Tailor the resume",
        status="running",
    )
    db_session.add(db_run)
    await db_session.flush()
    run = RunContext(
        run_id=db_run.id,
        tenant_id=sample_tenant.id,
        agent_name="tailor",
        goal=db_run.goal,
    )
    result = await agent_loop.step(session=db_session, run=run, provider="openrouter")

    assert result.observations[0]["tool_name"] == "blackboard_write"
    assert result.observations[0]["status"] == "success"
    assert result.reflections[0]["needs_correction"] is False


@pytest.mark.asyncio
async def test_loop_refuses_a_tool_outside_the_agent_allowlist(db_session, sample_tenant, monkeypatch):
    """A profiler cannot be talked into submitting an application."""
    await keyvault.store_key(db_session, sample_tenant.id, "openrouter", "sk-or-v1-live-example-key")

    async def fake_call(**kwargs):
        return LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(id="call_apply", name="ats_apply", arguments={"job_id": "job-1", "payload": {}})
            ],
        )

    monkeypatch.setattr(router, "call", fake_call)

    db_run = Run(
        id=str(uuid.uuid4()),
        tenant_id=sample_tenant.id,
        agent_name="profiler",
        goal="Fix the front face",
        status="running",
    )
    db_session.add(db_run)
    await db_session.flush()
    run = RunContext(
        run_id=db_run.id,
        tenant_id=sample_tenant.id,
        agent_name="profiler",
        goal=db_run.goal,
    )
    result = await agent_loop.step(session=db_session, run=run, provider="openrouter")

    assert result.status == "running"
    assert result.observations[0]["tool_name"] == "ats_apply"
    assert result.observations[0]["status"] == "error"
    assert result.reflections[0]["needs_correction"] is True


def _job():
    return SimpleNamespace(
        id="job-1",
        title="Machine Learning Engineer",
        company="Acme",
        description="Build pytorch ranking models and spark pipelines.",
    )


def _master():
    return {
        "candidate_name": "Ada",
        "contact_info": {"email": "ada@example.com"},
        "skills": ["Python", "PyTorch"],
        "experience": [
            {
                "company": "Acme",
                "dates": "2020-2024",
                "bullets": ["Shipped a pytorch ranking model."],
            }
        ],
        "education": [],
    }


@pytest.mark.asyncio
async def test_drafter_falls_back_when_openrouter_invents_a_company(monkeypatch):
    """A model draft that names a company absent from the master resume never becomes the packet."""
    async def fake_call(**kwargs):
        invented = {
            "candidate_name": "Ada",
            "contact_info": {"email": "ada@example.com"},
            "summary": "Staff engineer at Hallucinated Labs.",
            "skills": ["Python", "PyTorch"],
            "experience": [
                {
                    "company": "Hallucinated Labs",
                    "dates": "2020-2024",
                    "bullets": ["Shipped a pytorch ranking model."],
                }
            ],
            "education": [],
        }
        return LLMResponse(content=json.dumps(invented), tool_calls=[])

    monkeypatch.setattr(router, "call", fake_call)

    packet = await draft_application_packet(
        tenant_id="tenant-packet",
        master_content=_master(),
        job=_job(),
        verified_skills=["Python", "PyTorch"],
        raw_key="sk-or-v1-live-example-key",
    )

    companies = [item["company"] for item in packet["tailored_resume"]["experience"]]
    assert companies == ["Acme"]
    assert "Hallucinated Labs" not in packet["cover_letter"]["body_text"]
    assert packet["draft_source"] == "deterministic"
    assert packet["rejected_proposal"]["is_honest"] is False
    completed = packet["team"].board.list_tasks("tenant-packet", status="completed")
    assert [task.assigned_role for task in completed] == ["tailor", "reviewer", "cover"]


@pytest.mark.asyncio
async def test_drafter_keeps_an_honest_openrouter_resume(monkeypatch):
    """A model draft that stays inside the master facts is the version that gets a cover letter."""
    honest = {
        "candidate_name": "Ada",
        "contact_info": {"email": "ada@example.com"},
        "summary": "Machine learning engineer who shipped a pytorch ranking model at Acme.",
        "skills": ["PyTorch", "Python"],
        "experience": [
            {
                "company": "Acme",
                "dates": "2020-2024",
                "bullets": ["Shipped a pytorch ranking model."],
            }
        ],
        "education": [],
    }

    async def fake_call(**kwargs):
        assert kwargs["provider"] == "openrouter"
        assert kwargs["tier"] == "mid"
        return LLMResponse(content=json.dumps(honest), tool_calls=[])

    monkeypatch.setattr(router, "call", fake_call)

    packet = await draft_application_packet(
        tenant_id="tenant-honest",
        master_content=_master(),
        job=_job(),
        verified_skills=["Python", "PyTorch"],
        raw_key="sk-or-v1-live-example-key",
    )

    assert packet["draft_source"] == "openrouter"
    assert packet["honesty_review"]["is_honest"] is True
    assert "pytorch ranking model" in packet["tailored_resume"]["summary"]
    assert packet["rejected_proposal"] is None
    assert packet["models"]["reviewer"] == "deepseek/deepseek-r1"
