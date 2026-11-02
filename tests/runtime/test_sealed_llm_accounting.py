from __future__ import annotations

import asyncio

import pytest

from core.llm.contracts import LLMResponse, LLMUsage
from core.telemetry.event_types import LLM_COMPLETED, LLM_REQUESTED
from runtime._internal.effect_router import EffectRouter
from runtime._internal.effect_types import EffectActionType
from runtime._internal.effects_actions import llm_completion_support as module
from runtime.platform.event_store.memory_event_store import MemoryEventStore


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
    budget = module.EventStoreDailyTokenBudget(event_store=store, caps=module.BudgetCaps())
    assert budget.can_spend(tenant_id="tenant", user_id="admin", tokens=module.BudgetCaps().user_tokens_per_day - 20)
    assert not budget.can_spend(tenant_id="tenant", user_id="admin", tokens=module.BudgetCaps().user_tokens_per_day - 19)
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
        day = module.EventStoreDailyTokenBudget(event_store=store, caps=module.BudgetCaps())._day()
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
    assert result == {"ok": False, "error": "LLM_BUDGET_BLOCKED"}
    assert client.calls == 0
    assert store.count_events(tenant_id="tenant", event_type=LLM_REQUESTED) == 0


def test_budget_over_cap_handles_legacy_empty_pending_state():
    budget_store = MemoryEventStore()
    budget = module.EventStoreDailyTokenBudget(event_store=budget_store, caps=module.BudgetCaps())
    budget_store.set_setting(tenant_id="tenant", key=f"llm:pending:v1:{budget._day()}", value={})
    assert budget.reserve(tenant_id="tenant", user_id="admin", tokens=module.BudgetCaps().user_tokens_per_day + 1, request_id="oversized") is None
