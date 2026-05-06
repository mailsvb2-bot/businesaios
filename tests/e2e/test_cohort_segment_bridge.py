from __future__ import annotations

from core.behavior.cohorts.cohort_bridge import build_cohort_aggregates
from core.behavior.cohorts.cohort_sample import CohortSample
from core.behavior.cohorts.segment_direction import segment_direction_score


def test_cohort_segment_bridge_builds_direction() -> None:
    aggregates = build_cohort_aggregates(
        (
            CohortSample("seg_a", 0.8, 0.1, 0.7, 0.6),
            CohortSample("seg_a", 0.7, 0.2, 0.8, 0.5),
            CohortSample("seg_b", 0.3, 0.6, 0.4, 0.2),
        )
    )
    assert len(aggregates) == 2
    assert segment_direction_score(aggregates[0]) != 0.0
