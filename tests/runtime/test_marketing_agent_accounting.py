from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.llm.agent import LLMTaskContext, TaskType
from core.llm.contracts import LLMMessage, LLMRequest, LLMResponse, LLMUsage
from core.telemetry.event_types import LLM_COMPLETED, LLM_REQUESTED
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


@pytest.mark.parametrize("usage", [None, LLMUsage(), LLMUsage(prompt_tokens=-1, completion_tokens=4, total_tokens=3)])
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
