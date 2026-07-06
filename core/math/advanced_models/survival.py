from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class KaplanMeierPoint:
    time: float
    survival_probability: float


class KaplanMeierEstimator:
    def estimate(self, *, event_times: Sequence[float], observed: Sequence[int]) -> list[KaplanMeierPoint]:
        if len(event_times) != len(observed):
            raise ValueError("event_times and observed must have same length")
        rows = sorted((float(t), int(o)) for t, o in zip(event_times, observed, strict=False))
        at_risk = len(rows)
        survival = 1.0
        points: list[KaplanMeierPoint] = []
        i = 0
        while i < len(rows):
            t = rows[i][0]
            deaths = 0
            censored = 0
            while i < len(rows) and rows[i][0] == t:
                if rows[i][1] == 1:
                    deaths += 1
                else:
                    censored += 1
                i += 1
            if at_risk > 0 and deaths > 0:
                survival *= (at_risk - deaths) / at_risk
                points.append(KaplanMeierPoint(time=t, survival_probability=survival))
            at_risk -= deaths + censored
        return points


def exponential_hazard_probability(*, rate_lambda: float, time_horizon: float) -> float:
    if rate_lambda < 0:
        raise ValueError("rate_lambda must be >= 0")
    if time_horizon < 0:
        raise ValueError("time_horizon must be >= 0")
    return 1.0 - math.exp(-rate_lambda * time_horizon)


KaplanMeierEstimator.fit = KaplanMeierEstimator.estimate
