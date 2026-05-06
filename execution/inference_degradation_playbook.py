from __future__ import annotations

from dataclasses import dataclass

from execution.inference_capacity_contract import InferenceCapacityTier


CANON_INFERENCE_DEGRADATION_PLAYBOOK = True


@dataclass(frozen=True)
class InferenceDegradationDecision:
    target_tier: InferenceCapacityTier
    mode: str
    reason: str


class InferenceDegradationPlaybook:
    def evaluate(self, *, current_tier: InferenceCapacityTier, budget_pressure: bool, provider_failure: bool) -> InferenceDegradationDecision:
        if provider_failure and current_tier in {InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK, InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD}:
            return InferenceDegradationDecision(InferenceCapacityTier.LOCAL_GPU, 'provider_failover', 'provider_failure')
        if budget_pressure and current_tier not in {InferenceCapacityTier.CPU_FALLBACK, InferenceCapacityTier.LOCAL_GPU}:
            return InferenceDegradationDecision(InferenceCapacityTier.LOCAL_GPU, 'budget_guarded_degradation', 'budget_pressure')
        return InferenceDegradationDecision(current_tier, 'steady_state', 'no_degradation_needed')
    decide = evaluate
