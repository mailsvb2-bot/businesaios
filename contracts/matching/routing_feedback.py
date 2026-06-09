from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoutingFeedback:
    request_id: str = ""
    business_id: str = ""
    outcome_code: str = ""
    revenue: float = 0.0
    quality_score: float = 0.0
    response_latency_min: float = 0.0
