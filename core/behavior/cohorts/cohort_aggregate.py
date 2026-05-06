from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CohortAggregate:
    segment_key: str
    size: int
    mean_buy_vector: float
    mean_churn_vector: float
    mean_trust: float
    mean_payment_readiness: float
