from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from config.economics_world_model_policy import (
    DEFAULT_DOW_SEASONALITY_POLICY,
    DOWSeasonalityPolicy,
)

from .types import DemandObservation


class SeasonalityModel:
    def multiplier(self, *, dow: int | None = None, hour: int | None = None) -> float: ...


@dataclass(frozen=True)
class DOWSeasonalityModel:
    """Day-of-week seasonality multiplier.

    Multipliers are normalized around the neutral policy multiplier.
    """

    mult: dict[int, float]
    policy: DOWSeasonalityPolicy = DEFAULT_DOW_SEASONALITY_POLICY

    def multiplier(self, *, dow: int | None = None, hour: int | None = None) -> float:
        neutral_multiplier = self.policy.neutral_multiplier
        if dow is None:
            return neutral_multiplier
        try:
            return float(self.mult.get(int(dow), neutral_multiplier))
        except Exception:
            return neutral_multiplier

    @staticmethod
    def calibrate(
        observations: Iterable[DemandObservation],
        *,
        policy: DOWSeasonalityPolicy = DEFAULT_DOW_SEASONALITY_POLICY,
    ) -> DOWSeasonalityModel:
        sums: dict[int, float] = {}
        cnts: dict[int, float] = {}
        for observation in observations:
            dow = observation.context.dow
            if dow is None:
                continue
            day = int(dow)
            sums[day] = sums.get(day, policy.zero_accumulator) + float(observation.units)
            cnts[day] = cnts.get(day, policy.zero_accumulator) + policy.count_increment
        if not sums:
            return DOWSeasonalityModel(mult={}, policy=policy)

        avgs = {
            day: (
                sums[day]
                / max(policy.neutral_multiplier, cnts.get(day, policy.count_increment))
            )
            for day in sums
        }
        mean = sum(avgs.values()) / max(1, len(avgs))
        if mean <= 0:
            return DOWSeasonalityModel(mult={}, policy=policy)
        mult = {day: float(avgs[day] / mean) for day in avgs}
        return DOWSeasonalityModel(mult=mult, policy=policy)
