from __future__ import annotations

from collections import defaultdict

from core.behavior.cohorts.cohort_aggregate import CohortAggregate
from core.behavior.cohorts.cohort_sample import CohortSample


def build_cohort_aggregates(samples: tuple[CohortSample, ...]) -> tuple[CohortAggregate, ...]:
    grouped: dict[str, list[CohortSample]] = defaultdict(list)
    for item in samples:
        grouped[item.segment_key].append(item)

    out: list[CohortAggregate] = []
    for segment_key, entries in grouped.items():
        count = max(1, len(entries))
        out.append(
            CohortAggregate(
                segment_key=segment_key,
                size=len(entries),
                mean_buy_vector=sum(item.buy_vector for item in entries) / count,
                mean_churn_vector=sum(item.churn_vector for item in entries) / count,
                mean_trust=sum(item.trust for item in entries) / count,
                mean_payment_readiness=sum(item.payment_readiness for item in entries) / count,
            )
        )
    return tuple(sorted(out, key=lambda item: item.segment_key))
