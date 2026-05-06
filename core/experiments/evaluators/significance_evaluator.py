from __future__ import annotations

import math


class SignificanceEvaluator:
    def p_value_two_proportion(
        self,
        *,
        control_conversions: int,
        control_exposures: int,
        treatment_conversions: int,
        treatment_exposures: int,
    ) -> float:
        if control_exposures <= 0 or treatment_exposures <= 0:
            return 1.0
        pooled_n = control_exposures + treatment_exposures
        pooled_success = control_conversions + treatment_conversions
        if pooled_n <= 0:
            return 1.0
        pooled_p = pooled_success / pooled_n
        variance = pooled_p * (1.0 - pooled_p) * ((1.0 / control_exposures) + (1.0 / treatment_exposures))
        if variance <= 0.0:
            return 1.0
        control_rate = control_conversions / control_exposures
        treatment_rate = treatment_conversions / treatment_exposures
        z_score = (treatment_rate - control_rate) / math.sqrt(variance)
        cdf = 0.5 * (1.0 + math.erf(abs(z_score) / math.sqrt(2.0)))
        return max(0.0, min(1.0, 2.0 * (1.0 - cdf)))

    def is_significant(self, p_value: float, alpha: float = 0.05) -> bool:
        return p_value < alpha
