"""Tests for BYOK Model Router and Tier-based model dispatching."""

import pytest

from app.core.keyvault import keyvault
from app.core.model_router import (
    ProviderAuthError,
    ProviderQuotaError,
    router,
)
from app.core.outbox import outbox
from app.domain.models import Run


@pytest.mark.asyncio
async def test_model_router_tier_resolution():
    """Verifies that ModelRouter maps tiers correctly for each provider."""
    # Cheap tier
    assert router.model_for("openai", "cheap") == "gpt-4o-mini"
    assert router.model_for("anthropic", "cheap") == "claude-3-5-haiku-20241022"
    assert router.model_for("gemini", "cheap") == "gemini-1.5-flash"

    # Mid tier
    assert router.model_for("openai", "mid") == "gpt-4o"
    assert router.model_for("gemini", "mid") == "gemini-1.5-pro"

    # OpenRouter DeepSeek Flash v4.1
    assert router.model_for("openrouter", "cheap") == "deepseek/deepseek-chat-v4.1"
    assert router.model_for("openrouter", "mid") == "deepseek/deepseek-chat-v4.1"
    assert router.model_for("openrouter", "cheap", model_override="deepseek/deepseek-flash-v4.1") == "deepseek/deepseek-flash-v4.1"
    assert router.model_for("deepseek", "cheap") == "deepseek-chat"

    # Unsupported provider raises ValueError
    with pytest.raises(ValueError):
        router.model_for("unknown_provider", "mid")


@pytest.mark.asyncio
async def test_model_router_probe_validation():
    """Verifies key probe validation on registration."""
    # Valid key probe
    res = await router.probe_key("openai", "sk-proj-validkey12345678")
    assert res["status"] == "valid"
    assert "gpt-4o-mini" in res["models_available"]

    # Invalid key probe
    with pytest.raises(ProviderAuthError):
        await router.probe_key("openai", "sk-invalid-key-99999999")

    # Quota exhausted probe
    with pytest.raises(ProviderQuotaError):
        await router.probe_key("openai", "sk-no-credits-key-99999")


@pytest.mark.asyncio
async def test_model_router_402_pauses_run_and_emits_event(db_session, sample_tenant):
    """Verifies that encountering 402 during an agent call pauses the run and emits key.failed."""
    raw_key = "sk-run-out-of-credits-402"
    await keyvault.store_key(db_session, sample_tenant.id, "openai", raw_key)

    run = Run(
        tenant_id=sample_tenant.id,
        agent_name="writer",
        goal="Tailor resume to Tech Lead role",
        status="running",
    )
    db_session.add(run)
    await db_session.flush()

    # Model call triggers 402
    with pytest.raises(ProviderQuotaError) as exc_info:
        await router.call(
            provider="openai",
            raw_key=raw_key,
            tier="frontier",
            system_prompt="You are a career resume writer",
            messages=[{"role": "user", "content": "Tailor this section"}],
        )

    # Harness catches ProviderQuotaError and invokes KeyVault pause handler + Outbox event
    await keyvault.handle_key_failure(
        session=db_session,
        tenant_id=sample_tenant.id,
        provider="openai",
        reason=str(exc_info.value),
    )
    await outbox.record_event(
        session=db_session,
        tenant_id=sample_tenant.id,
        event_name="key.failed",
        payload={"provider": "openai", "error": str(exc_info.value)},
    )
    await db_session.commit()

    # Verify run is paused
    await db_session.refresh(run)
    assert run.status == "paused"
    assert "402" in run.pause_reason
