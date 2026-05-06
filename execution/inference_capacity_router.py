from __future__ import annotations

from dataclasses import dataclass

from execution.inference_capacity_contract import InferenceCapacitySelection, InferenceCapacityTier
from execution.inference_capacity_policy import InferenceCapacityPolicy, InferenceCapacityPolicyContext
from execution.inference_complexity_estimator import InferenceComplexityEstimator
from execution.inference_cost_estimator import InferenceCostEstimator
from execution.inference_provider_contract import InferenceProvider
from execution.inference_workload_contract import InferenceWorkloadDescriptor


CANON_INFERENCE_CAPACITY_ROUTER = True


@dataclass(frozen=True)
class _ProviderCandidate:
    provider: InferenceProvider
    healthy: bool
    error_rate: float
    availability_score: float
    estimated_cost_usd: float


class NoInferenceProviderAvailableError(RuntimeError):
    pass


class InferenceCapacityRouter:
    def __init__(
        self,
        *,
        providers: dict[str, InferenceProvider],
        capacity_policy: InferenceCapacityPolicy | None = None,
        complexity_estimator: InferenceComplexityEstimator | None = None,
        cost_estimator: InferenceCostEstimator | None = None,
    ) -> None:
        self._providers = dict(providers)
        self._capacity_policy = capacity_policy or InferenceCapacityPolicy()
        self._complexity_estimator = complexity_estimator or InferenceComplexityEstimator()
        self._cost_estimator = cost_estimator or InferenceCostEstimator()

    def route_capacity(
        self,
        *,
        workload: InferenceWorkloadDescriptor,
        preferred_tier: InferenceCapacityTier,
        policy_context: InferenceCapacityPolicyContext,
    ) -> InferenceCapacitySelection:
        requirement = self._complexity_estimator.estimate(workload)
        candidates: list[_ProviderCandidate] = []
        for provider in self._providers.values():
            if provider.profile.tier != preferred_tier:
                continue
            if not self._capacity_policy.allows(policy_context, provider.profile.tier):
                continue
            limits = provider.profile.limits
            if limits.max_context_tokens < requirement.required_context_tokens:
                continue
            if limits.max_output_tokens < requirement.required_output_tokens:
                continue
            if limits.max_batch_items < requirement.required_batch_items:
                continue
            health = provider.health()
            candidates.append(
                _ProviderCandidate(
                    provider=provider,
                    healthy=health.healthy,
                    error_rate=health.error_rate,
                    availability_score=health.availability_score,
                    estimated_cost_usd=self._cost_estimator.estimate(profile=provider.profile, requirement=requirement),
                )
            )
        if not candidates:
            cpu_provider = next(
                (item for item in self._providers.values() if item.profile.tier == InferenceCapacityTier.CPU_FALLBACK),
                None,
            )
            if cpu_provider is None:
                raise NoInferenceProviderAvailableError('CPU fallback provider is required but not registered.')
            return InferenceCapacitySelection(
                tier=cpu_provider.profile.tier,
                provider_name=cpu_provider.name,
                reason='No suitable provider found at preferred tier; canonical fallback to CPU.',
                estimated_cost_usd=self._cost_estimator.estimate(profile=cpu_provider.profile, requirement=requirement),
            )
        selected = sorted(
            candidates,
            key=lambda item: (item.healthy is False, -item.availability_score, item.error_rate, item.estimated_cost_usd),
        )[0]
        return InferenceCapacitySelection(
            tier=selected.provider.profile.tier,
            provider_name=selected.provider.name,
            reason='Selected by deterministic inference capacity router.',
            estimated_cost_usd=selected.estimated_cost_usd,
        )


InferenceCapacityRouter.select = InferenceCapacityRouter.route_capacity
