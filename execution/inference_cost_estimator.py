from __future__ import annotations

from execution.inference_capacity_contract import InferenceCapacityProfile, InferenceCapacityRequirement


CANON_INFERENCE_COST_ESTIMATOR = True


class InferenceCostEstimator:
    def estimate(self, *, profile: InferenceCapacityProfile, requirement: InferenceCapacityRequirement) -> float:
        total_tokens = requirement.required_context_tokens + requirement.required_output_tokens
        return round((float(total_tokens) / 1000.0) * profile.estimated_cost_per_1k_tokens_usd, 6)
