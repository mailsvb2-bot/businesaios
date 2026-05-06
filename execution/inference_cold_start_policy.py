from __future__ import annotations

from dataclasses import dataclass

from execution.inference_capacity_contract import InferenceCapacityTier


CANON_INFERENCE_COLD_START_POLICY = True


@dataclass(frozen=True)
class InferenceColdStartDecision:
    preferred_tier: InferenceCapacityTier
    reason: str


class InferenceColdStartPolicy:
    def evaluate(self, *, historical_executions: int, requested_tier: InferenceCapacityTier) -> InferenceColdStartDecision:
        if historical_executions < 10 and requested_tier not in {
            InferenceCapacityTier.CPU_FALLBACK,
            InferenceCapacityTier.LOCAL_GPU,
        }:
            return InferenceColdStartDecision(
                preferred_tier=InferenceCapacityTier.LOCAL_GPU,
                reason='cold_start_conservative_downgrade',
            )
        return InferenceColdStartDecision(preferred_tier=requested_tier, reason='cold_start_ok')
    decide = evaluate
