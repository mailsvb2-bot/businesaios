from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CohortSample:
    segment_key: str
    buy_vector: float
    churn_vector: float
    trust: float
    payment_readiness: float
