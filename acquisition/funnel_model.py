from __future__ import annotations

import math
from dataclasses import dataclass

from shared.numbers import coerce_float, coerce_int

CANON_ACQUISITION_FUNNEL_MODEL = True


@dataclass(frozen=True, slots=True)
class FunnelStage:
    name: str
    conversion_rate: float
    avg_stage_days: float = 0.0
    touchpoints: int = 1


@dataclass(frozen=True, slots=True)
class FunnelSnapshot:
    stage_count: int
    overall_conversion_rate: float
    avg_cycle_days: float
    touchpoints_per_customer: int
    stage_dropoffs: tuple[tuple[str, float], ...]

    def required_entries_for_customers(self, customers: int) -> int:
        customers = coerce_int(customers, 0, minimum=0)
        if customers <= 0:
            return 0
        if self.overall_conversion_rate <= 0.0:
            return 0
        return int(math.ceil(customers / self.overall_conversion_rate))

    def expected_customers_from_entries(self, entries: int) -> int:
        entries = coerce_int(entries, 0, minimum=0)
        if entries <= 0 or self.overall_conversion_rate <= 0.0:
            return 0
        return int(entries * self.overall_conversion_rate)


class FunnelModel:
    def summarize(self, stages: tuple[FunnelStage, ...] | list[FunnelStage]) -> FunnelSnapshot:
        if not stages:
            return FunnelSnapshot(
                stage_count=0,
                overall_conversion_rate=0.0,
                avg_cycle_days=0.0,
                touchpoints_per_customer=0,
                stage_dropoffs=(),
            )
        normalized: list[FunnelStage] = []
        for item in stages:
            normalized.append(
                FunnelStage(
                    name=str(item.name or "stage"),
                    conversion_rate=coerce_float(item.conversion_rate, 0.0, minimum=0.0, maximum=1.0),
                    avg_stage_days=coerce_float(item.avg_stage_days, 0.0, minimum=0.0),
                    touchpoints=coerce_int(item.touchpoints, 1, minimum=1),
                )
            )
        overall_conversion_rate = 1.0
        total_days = 0.0
        total_touchpoints = 0
        dropoffs: list[tuple[str, float]] = []
        for stage in normalized:
            overall_conversion_rate *= stage.conversion_rate
            total_days += stage.avg_stage_days
            total_touchpoints += stage.touchpoints
            dropoffs.append((stage.name, round(1.0 - stage.conversion_rate, 4)))
        return FunnelSnapshot(
            stage_count=len(normalized),
            overall_conversion_rate=round(overall_conversion_rate, 6),
            avg_cycle_days=round(total_days, 4),
            touchpoints_per_customer=total_touchpoints,
            stage_dropoffs=tuple(dropoffs),
        )
