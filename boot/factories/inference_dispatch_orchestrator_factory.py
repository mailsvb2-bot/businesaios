from __future__ import annotations

from execution.inference_dispatch_orchestrator import InferenceDispatchOrchestrator
from execution.inference_fallback_chain import InferenceFallbackChain
from execution.inference_policy_guard import InferencePolicyGuard
from runtime.inference.providers.provider_circuit_breaker import ProviderCircuitBreaker
from runtime.inference.providers.provider_rate_limit_guard import ProviderRateLimitGuard
from runtime.inference.providers.provider_retry_adapter import ProviderRetryAdapter, RetryPolicy
from runtime.inference.providers.provider_registry import InferenceProviderRegistry
from execution.inference_capacity_router import InferenceCapacityRouter
from observability.inference_acceleration_log import InferenceAccelerationLog


def build_inference_dispatch_orchestrator(
    *,
    registry: InferenceProviderRegistry,
    router: InferenceCapacityRouter,
) -> InferenceDispatchOrchestrator:
    return InferenceDispatchOrchestrator(
        providers=registry.as_dict(),
        router=router,
        policy_guard=InferencePolicyGuard(),
        retry_adapter=ProviderRetryAdapter(RetryPolicy(max_attempts=2, backoff_seconds=0.0)),
        circuit_breaker=ProviderCircuitBreaker(),
        rate_limit_guard=ProviderRateLimitGuard(),
        fallback_chain=InferenceFallbackChain(),
        acceleration_log=InferenceAccelerationLog(),
    )


__all__ = ['build_inference_dispatch_orchestrator']
