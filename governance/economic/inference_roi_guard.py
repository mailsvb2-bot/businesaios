from __future__ import annotations

from dataclasses import dataclass


CANON_GOVERNANCE_INFERENCE_ROI_GUARD = True


@dataclass(frozen=True)
class InferenceROIGuard:
    min_expected_value_ratio: float = 1.25

    def allows(self, *, expected_benefit_usd: float, expected_cost_usd: float) -> bool:
        if expected_cost_usd <= 0.0:
            return True
        return (float(expected_benefit_usd) / float(expected_cost_usd)) >= self.min_expected_value_ratio
