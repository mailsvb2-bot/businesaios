from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrendSignal:
    source: str
    segment_key: str
    demand_delta: float
    conversion_delta: float
    cpm_delta: float
    cpc_delta: float
    competitor_pressure: float
    recency_weight: float = 1.0
