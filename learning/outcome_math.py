from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Hashable, Sequence

from core.math.advanced_models import (
    KaplanMeierEstimator,
    estimate_difference_in_means_uplift,
    exponential_hazard_probability,
    q_learning_update,
)


@dataclass
class OutcomeMathSupport:
    q_table: Dict[Hashable, Dict[Hashable, float]] = field(default_factory=dict)

    def q_update(
        self,
        *,
        state: Hashable,
        action: Hashable,
        reward: float,
        next_state: Hashable,
        next_actions: Sequence[Hashable],
        alpha: float = 0.1,
        gamma: float = 0.95,
    ) -> float:
        return q_learning_update(
            self.q_table,
            state=state,
            action=action,
            reward=float(reward),
            next_state=next_state,
            next_actions=next_actions,
            alpha=float(alpha),
            gamma=float(gamma),
        )

    def uplift(self, *, treatment_outcomes: Sequence[float], control_outcomes: Sequence[float]) -> float:
        return float(
            estimate_difference_in_means_uplift(
                treatment_outcomes=treatment_outcomes,
                control_outcomes=control_outcomes,
            ).uplift
        )

    def conversion_probability(self, *, rate_lambda: float, horizon_days: float) -> float:
        return float(exponential_hazard_probability(rate_lambda=float(rate_lambda), time_horizon=float(horizon_days)))

    def survival_curve(self, *, event_times: Sequence[float], observed: Sequence[int]) -> tuple[tuple[float, float], ...]:
        km = KaplanMeierEstimator().fit(event_times=event_times, observed=observed)
        return tuple((float(point.time), float(point.survival_probability)) for point in km)
