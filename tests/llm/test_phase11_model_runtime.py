from __future__ import annotations

import asyncio

import pytest

from core.llm import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMUsage,
    ModelCapability,
    ModelCapabilityRegistry,
    ModelEvaluation,
    ModelPolicy,
    ModelProfile,
    ModelRouter,
    ModelRouteRequest,
)
from core.telemetry.event_types import LLM_COMPLETED
from runtime.llm import RoutedLLMClient
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class _BudgetMarkedMemoryStore(MemoryEventStore):
    """Test double that opts into the durable LLM budget contract (#560)."""

    supports_durable_llm_budget = True


def _profile(
    profile_id: str,
    *,
    provider: str,
    model: str,
    cost: float,
    latency_ms: int = 100,
    available: bool = True,
) -> ModelProfile:
    return ModelProfile(
        profile_id=profile_id,
        provider=provider,
        model=model,
        model_version="2026-10-02",
        capabilities=frozenset({ModelCapability.STRUCTURED_OUTPUT}),
        quality_score=0.9,
        input_cost_per_1k_tokens=cost,
        output_cost_per_1k_tokens=cost,
        typical_latency_ms=latency_ms,
        privacy_class="internal",
        risk_score=0.1,
        max_context_tokens=32_000,
        availability=available,
        historical_success_rate=0.9,
        jurisdictions=frozenset({"*"}),
    )


def test_router_uses_cheapest_eligible_profile_and_makes_fallback_observable() -> None:
    expensive = _profile(
        "frontier",
        provider="provider-a",
        model="frontier-v1",
        cost=0.05,
        available=False,
    )
    economical = _profile(
        "economical",
        provider="provider-b",
        model="economical-v1",
        cost=0.005,
    )
    router = ModelRouter(ModelCapabilityRegistry([expensive, economical]))

    decision = router.route(
        ModelRouteRequest(
            required_capabilities=frozenset({ModelCapability.STRUCTURED_OUTPUT}),
            context_tokens=1_000,
            estimated_input_tokens=500,
            estimated_output_tokens=250,
            preferred_profile_id="frontier",
        ),
        policy=ModelPolicy(policy_id="phase11", version="1"),
    )

    assert decision.profile.profile_id == "economical"
    assert decision.fallback_observable is True
    assert decision.fallback_from_profile_id == "frontier"
    assert decision.estimated_cost == pytest.approx(0.00375)


def test_pinned_profile_fails_closed_when_it_is_not_eligible() -> None:
    unavailable = _profile(
        "pinned",
        provider="provider-a",
        model="pinned-v1",
        cost=0.01,
        available=False,
    )
    router = ModelRouter(ModelCapabilityRegistry([unavailable]))

    with pytest.raises(RuntimeError, match="pinned model profile is not eligible"):
        router.route(
            ModelRouteRequest(
                required_capabilities=frozenset({ModelCapability.STRUCTURED_OUTPUT}),
                pinned_profile_id="pinned",
            ),
            policy=ModelPolicy(policy_id="critical", version="7"),
        )


def test_degraded_structured_output_profile_is_excluded() -> None:
    degraded = _profile(
        "degraded",
        provider="provider-a",
        model="degraded-v1",
        cost=0.001,
    )
    healthy = _profile(
        "healthy",
        provider="provider-b",
        model="healthy-v1",
        cost=0.01,
    )
    router = ModelRouter(
        ModelCapabilityRegistry([degraded, healthy]),
        evaluations={
            "degraded": ModelEvaluation(
                profile_id="degraded",
                structured_output_success_rate=0.5,
            ),
            "healthy": ModelEvaluation(
                profile_id="healthy",
                structured_output_success_rate=0.99,
            ),
        },
    )

    decision = router.route(
        ModelRouteRequest(
            required_capabilities=frozenset({ModelCapability.STRUCTURED_OUTPUT}),
        ),
        policy=ModelPolicy(
            policy_id="structured",
            version="3",
            min_structured_output_success_rate=0.95,
        ),
    )

    assert decision.profile.profile_id == "healthy"


class _CaptureClient:
    def __init__(self) -> None:
        self.request: LLMRequest | None = None
        self.async_calls = 0

    def generate_sync(self, req: LLMRequest) -> LLMResponse:
        self.request = req
        return LLMResponse(content="ok", usage=LLMUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5), raw={"provider_receipt": "r-1"})

    async def generate(self, req: LLMRequest) -> LLMResponse:
        self.async_calls += 1
        return self.generate_sync(req)


def test_routed_client_records_model_version_policy_and_route() -> None:
    profile = _profile(
        "canonical",
        provider="provider-a",
        model="canonical-v2",
        cost=0.01,
    )
    client = _CaptureClient()
    store = _BudgetMarkedMemoryStore()
    routed = RoutedLLMClient(
        router=ModelRouter(ModelCapabilityRegistry([profile])),
        clients_by_profile_id={"canonical": client},
        policy=ModelPolicy(policy_id="prod", version="11"),
        event_store=store,
    )
    request = LLMRequest(
        messages=[LLMMessage(role="user", content="hello")],
        model="legacy-placeholder",
        max_tokens=100,
        metadata={
            "required_model_capabilities": ("structured_output",),
            "context_tokens": 50,
            "tenant_id": "tenant-a",
            "user_id": "owner-1",
            "correlation_key": "decision-1",
            "task_type": "model_route_test",
        },
    )

    response = routed.generate_sync(request)

    assert client.request is not None
    assert client.request.model == "canonical-v2"
    assert client.request.model_profile_id == "canonical"
    assert client.request.metadata is not None
    assert client.request.metadata["model_version"] == "2026-10-02"
    assert client.request.metadata["model_policy_id"] == "prod"
    assert client.request.metadata["model_policy_version"] == "11"
    assert response.raw is not None
    assert response.raw["provider_receipt"] == "r-1"
    assert response.raw["model_route"]["profile_id"] == "canonical"
    completed = list(store.iter_events(tenant_id="tenant-a", event_type=LLM_COMPLETED))
    assert len(completed) == 1
    assert completed[0]["payload"]["provider"] == "provider-a"
    assert completed[0]["payload"]["model"] == "canonical-v2"
    assert completed[0]["payload"]["total_tokens"] == 5


def test_routed_client_fails_closed_before_provider_call_without_identity() -> None:
    profile = _profile("canonical", provider="provider-a", model="canonical-v2", cost=0.01)
    client = _CaptureClient()
    routed = RoutedLLMClient(
        router=ModelRouter(ModelCapabilityRegistry([profile])),
        clients_by_profile_id={"canonical": client},
        policy=ModelPolicy(policy_id="prod", version="11"),
        event_store=_BudgetMarkedMemoryStore(),
    )
    request = LLMRequest(
        messages=[LLMMessage(role="user", content="hello")],
        model="legacy-placeholder",
        metadata={"required_model_capabilities": ("structured_output",)},
    )
    with pytest.raises(RuntimeError, match="LLM_ACCOUNTING_UNAVAILABLE"):
        routed.generate_sync(request)
    assert client.request is None


def test_routed_client_async_uses_the_same_accounted_gateway() -> None:
    profile = _profile("canonical", provider="provider-a", model="canonical-v2", cost=0.01)
    client = _CaptureClient()
    store = _BudgetMarkedMemoryStore()
    routed = RoutedLLMClient(
        router=ModelRouter(ModelCapabilityRegistry([profile])),
        clients_by_profile_id={"canonical": client},
        policy=ModelPolicy(policy_id="prod", version="11"),
        event_store=store,
    )
    request = LLMRequest(
        messages=[LLMMessage(role="user", content="hello")],
        model="legacy-placeholder",
        max_tokens=100,
        metadata={
            "required_model_capabilities": ("structured_output",),
            "tenant_id": "tenant-a",
            "user_id": "owner-1",
            "correlation_key": "decision-async",
            "task_type": "model_route_test",
        },
    )
    response = asyncio.run(routed.generate(request))
    assert response.content == "ok"
    assert client.request is not None and client.request.model == "canonical-v2"
    assert client.async_calls == 0
    completed = list(store.iter_events(tenant_id="tenant-a", event_type=LLM_COMPLETED))
    assert len(completed) == 1
    assert completed[0]["payload"]["total_tokens"] == 5
