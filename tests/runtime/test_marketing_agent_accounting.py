from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from core.llm.agent import LLMTaskContext, TaskType
from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget
from core.llm.contracts import LLMMessage, LLMRequest, LLMResponse, LLMUsage
from core.telemetry.event_types import LLM_COMPLETED, LLM_REQUESTED
from runtime._internal.effect_router import EffectRouter
from runtime._internal.effect_types import EffectActionType
from runtime._internal.effects_actions import llm_completion_support as module
from runtime.boot.builders import marketing_llm as builder
from runtime.llm import AccountedSyncGateway
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class Provider:
    def __init__(self):
        self.calls = 0

    def generate_sync(self, request):
        self.calls += 1
        return LLMResponse(content="safe text", usage=LLMUsage(prompt_tokens=13, completion_tokens=7, total_tokens=20))


def request(**metadata):
    return LLMRequest(model="mock", messages=[LLMMessage(role="user", content="hello")],
                      metadata={"tenant_id": "tenant", "user_id": "user", "correlation_key": "event-1",
                                "task_type": "ads.creative.generate", **metadata})


def test_agent_gateway_records_actual_usage_once_and_isolates_tenants():
    store, client = MemoryEventStore(), Provider()
    gateway = AccountedSyncGateway(client, event_store=store, provider="openai_compat")
    assert gateway.generate_sync(request()).content == "safe text"
    with pytest.raises(RuntimeError, match="LLM_BUDGET_BLOCKED"):
        gateway.generate_sync(request())
    assert client.calls == 1
    assert store.count_events(tenant_id="tenant", event_type=LLM_COMPLETED) == 1
    assert store.sum_event_payload_int(tenant_id="tenant", event_type=LLM_COMPLETED,
                                       field="total_tokens", user_id="user") == 20
    assert gateway.generate_sync(request(tenant_id="other")).content == "safe text"
    assert client.calls == 2


@pytest.mark.parametrize("missing", ["tenant_id", "user_id", "correlation_key", "task_type"])
def test_agent_gateway_fails_closed_without_scoped_identity(missing):
    store, client = MemoryEventStore(), Provider()
    gateway = AccountedSyncGateway(client, event_store=store, provider="openai_compat")
    with pytest.raises(RuntimeError, match="LLM_ACCOUNTING_UNAVAILABLE"):
        gateway.generate_sync(request(**{missing: ""}))
    assert client.calls == 0


@pytest.mark.parametrize("failed_event, expected_calls", [(LLM_REQUESTED, 0), (LLM_COMPLETED, 1)])
def test_agent_gateway_journal_failure_blocks_output_and_replay(failed_event, expected_calls):
    class BrokenStore(MemoryEventStore):
        def append_event(self, event):
            if event.get("event_type") == failed_event:
                raise OSError("journal unavailable")
            return super().append_event(event)

    store, client = BrokenStore(), Provider()
    gateway = AccountedSyncGateway(client, event_store=store, provider="openai_compat")
    with pytest.raises(RuntimeError, match="LLM_ACCOUNTING_UNAVAILABLE"):
        gateway.generate_sync(request())
    assert client.calls == expected_calls
    with pytest.raises(RuntimeError, match="LLM_BUDGET_BLOCKED"):
        gateway.generate_sync(request())
    assert client.calls == expected_calls


@pytest.mark.parametrize("usage", [None, LLMUsage(),
    LLMUsage(prompt_tokens=-1, completion_tokens=4, total_tokens=3),
    LLMUsage(prompt_tokens=13, completion_tokens=7, total_tokens=0),
    LLMUsage(prompt_tokens=13, completion_tokens=7, total_tokens=19)])
def test_gateway_missing_or_invalid_provider_usage_never_fabricates_spend(usage):
    class Unreported(Provider):
        def generate_sync(self, request):
            self.calls += 1
            return LLMResponse(content="unsafe to release", usage=usage)

    store, client = MemoryEventStore(), Unreported()
    gateway = AccountedSyncGateway(client, event_store=store, provider="openai_compat")
    with pytest.raises(RuntimeError, match="LLM_ACCOUNTING_UNAVAILABLE"):
        gateway.generate_sync(request())
    assert store.count_events(tenant_id="tenant", event_type=LLM_COMPLETED) == 0
    with pytest.raises(RuntimeError, match="LLM_BUDGET_BLOCKED"):
        gateway.generate_sync(request())
    assert client.calls == 1


def test_boot_marketing_agent_uses_same_durable_gateway(monkeypatch):
    store, client = MemoryEventStore(), Provider()
    monkeypatch.setattr(builder, "build_marketing_llm_composer",
                        lambda **kw: SimpleNamespace(llm_client=client))
    monkeypatch.setattr(builder, "_provider_settings",
                        lambda settings: ("openai_compat", "", "", "mock", None))
    agent = builder.build_marketing_llm_agent(settings=SimpleNamespace(), event_store=store, logger=None)
    ctx = LLMTaskContext(tenant_id="tenant", user_id="user", correlation_key="creative-1")
    assert agent.run_task(TaskType.ADS_CREATIVE_GENERATE, ctx).text == "safe text"
    with pytest.raises(RuntimeError, match="LLM_BUDGET_BLOCKED"):
        agent.run_task(TaskType.ADS_CREATIVE_GENERATE, ctx)
    assert client.calls == 1
    assert store.count_events(tenant_id="tenant", event_type=LLM_COMPLETED) == 1

class _Provider:
    calls = 0

    def generate_sync(self, request):
        self.calls += 1
        return LLMResponse(content="safe text", usage=LLMUsage(prompt_tokens=13, completion_tokens=7, total_tokens=20))


def _invoke(store, *, decision_id="decision-1", tenant="tenant", admin="admin"):
    router = EffectRouter(llm_accounting_store=store, llm_tenant_id=tenant)
    return asyncio.run(router.execute(EffectActionType.LLM_MARKETING_COMPLETE, {
        "provider": "openai_compat", "system": "system", "user": "user", "model": "mock",
        "admin_id": admin, "decision_id": decision_id,
    }))


def test_sealed_effect_fails_closed_without_event_store(monkeypatch):
    client = _Provider()
    monkeypatch.setattr(module, "_client_for", lambda **kw: ("openai_compat", "mock", client, None))
    assert _invoke(None)["ok"] is False
    assert client.calls == 0


def test_sealed_effect_records_actual_usage_once_and_blocks_replay(monkeypatch):
    store = MemoryEventStore()
    client = _Provider()
    monkeypatch.setattr(module, "_client_for", lambda **kw: ("openai_compat", "mock", client, None))
    assert _invoke(store)["ok"] is True
    assert _invoke(store)["ok"] is False
    assert client.calls == 1
    assert store.sum_event_payload_int(tenant_id="tenant", event_type=LLM_COMPLETED, field="total_tokens", user_id="admin") == 20
    assert store.count_events(tenant_id="tenant", event_type=LLM_COMPLETED) == 1
    assert store.count_events(tenant_id="tenant", event_type=LLM_REQUESTED) == 1
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    assert budget.can_spend(tenant_id="tenant", user_id="admin", tokens=BudgetCaps().user_tokens_per_day - 20)
    assert not budget.can_spend(tenant_id="tenant", user_id="admin", tokens=BudgetCaps().user_tokens_per_day - 19)
    assert _invoke(store, decision_id="decision-1", tenant="other")["ok"] is True
    assert client.calls == 2


@pytest.mark.parametrize("failed_event, expected_calls", [(LLM_REQUESTED, 0), (LLM_COMPLETED, 1)])
def test_sealed_effect_journal_failure_is_fail_closed(monkeypatch, failed_event, expected_calls):
    class BrokenStore(MemoryEventStore):
        def append_event(self, event):
            if event.get("event_type") == failed_event:
                raise OSError("journal unavailable")
            return super().append_event(event)

    store, client = BrokenStore(), _Provider()
    monkeypatch.setattr(module, "_client_for", lambda **kw: ("openai_compat", "mock", client, None))
    assert _invoke(store)["ok"] is False
    assert client.calls == expected_calls
    if failed_event == LLM_REQUESTED:
        day = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())._day()
        assert store.get_setting(tenant_id="tenant", key=f"llm:pending:v1:{day}") == {"pending": {}}
    else:
        assert _invoke(store)["ok"] is False
        assert client.calls == 1


def test_sealed_effect_reserves_worst_case_prompt_before_provider(monkeypatch):
    # A short fixed 800-token input allowance permits concurrent long prompts
    # that can exceed the daily cap even when output is limited to 600 tokens.
    store, client = MemoryEventStore(), _Provider()
    monkeypatch.setattr(module, "_client_for", lambda **kw: ("openai_compat", "mock", client, None))
    result = module.call_marketing_llm(
        provider="openai_compat", system="x" * 8000, user="y" * 8000,
        model="mock", event_store=store, tenant_id="tenant", user_id="admin",
        request_id="long-input",
    )
    assert result["ok"] is False
    assert result["error"] == "LLM_BUDGET_BLOCKED"
    assert client.calls == 0
    assert store.count_events(tenant_id="tenant", event_type=LLM_REQUESTED) == 0


def test_budget_over_cap_handles_legacy_empty_pending_state():
    budget_store = MemoryEventStore()
    budget = EventStoreDailyTokenBudget(event_store=budget_store, caps=BudgetCaps())
    budget_store.set_setting(tenant_id="tenant", key=f"llm:pending:v1:{budget._day()}", value={})
    assert budget.reserve(tenant_id="tenant", user_id="admin", tokens=BudgetCaps().user_tokens_per_day + 1, request_id="oversized") is None
