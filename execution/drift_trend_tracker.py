from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANON_HEADLESS_DRIFT_TREND_TRACKER = True


@dataclass(frozen=True)
class DriftTrendSummary:
    samples: int
    avg_goal_score_delta: float
    high_count: int
    medium_count: int
    low_count: int
    none_count: int
    summary: str


@dataclass(frozen=True)
class DriftTrendTracker:
    """
    Aggregates many drift reports into a compact trend summary.

    Analysis only. Never affects execution.
    """

    def summarize(self, *, drift_reports: list[Any]) -> DriftTrendSummary:
        samples = len(drift_reports)
        if samples == 0:
            return DriftTrendSummary(
                samples=0,
                avg_goal_score_delta=0.0,
                high_count=0,
                medium_count=0,
                low_count=0,
                none_count=0,
                summary="no drift samples",
            )

        total_delta = 0.0
        high_count = 0
        medium_count = 0
        low_count = 0
        none_count = 0

        for report in drift_reports:
            total_delta += float(getattr(report, "goal_score_delta", 0.0))
            severity = str(getattr(report, "severity", "none"))
            if severity == "high":
                high_count += 1
            elif severity == "medium":
                medium_count += 1
            elif severity == "low":
                low_count += 1
            else:
                none_count += 1

        avg = total_delta / float(samples)
        summary = (
            f"samples={samples}, avg_goal_score_delta={avg:.3f}, "
            f"high={high_count}, medium={medium_count}, low={low_count}, none={none_count}"
        )
        return DriftTrendSummary(
            samples=samples,
            avg_goal_score_delta=float(avg),
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            none_count=none_count,
            summary=summary,
        )


__all__ = [
    "CANON_HEADLESS_DRIFT_TREND_TRACKER",
    "DriftTrendSummary",
    "DriftTrendTracker",
]
