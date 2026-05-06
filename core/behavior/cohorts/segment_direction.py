from __future__ import annotations

from core.behavior.cohorts.cohort_aggregate import CohortAggregate


def segment_direction_score(item: CohortAggregate) -> float:
    score = (
        0.45 * float(item.mean_buy_vector)
        + 0.25 * float(item.mean_trust)
        + 0.20 * float(item.mean_payment_readiness)
        - 0.30 * float(item.mean_churn_vector)
    )
    return max(-1.0, min(1.0, score))
