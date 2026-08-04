from __future__ import annotations

import math
from dataclasses import dataclass


def _finite(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def wilson_interval(
    successes: int,
    total: int,
    z: float = 1.959963984540054,
) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 1.0)
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = p + z * z / (2.0 * total)
    margin = z * math.sqrt(
        (p * (1.0 - p) + z * z / (4.0 * total)) / total
    )
    return ((centre - margin) / denominator, (centre + margin) / denominator)


def difference_lower_bound(
    candidate_successes: int,
    candidate_total: int,
    control_successes: int,
    control_total: int,
    z: float = 1.959963984540054,
) -> float:
    if candidate_total <= 0 or control_total <= 0:
        return float("-inf")
    candidate_rate = candidate_successes / candidate_total
    control_rate = control_successes / control_total
    variance = (
        candidate_rate * (1.0 - candidate_rate) / candidate_total
        + control_rate * (1.0 - control_rate) / control_total
    )
    return candidate_rate - control_rate - z * math.sqrt(max(0.0, variance))


def sample_ratio_z(
    candidate_count: int,
    total: int,
    expected_fraction: float,
) -> float:
    if total <= 0 or not 0.0 < expected_fraction < 1.0:
        return 0.0
    expected = total * expected_fraction
    variance = total * expected_fraction * (1.0 - expected_fraction)
    if variance <= 0:
        return 0.0
    return (candidate_count - expected) / math.sqrt(variance)


@dataclass(frozen=True)
class ArmStatistics:
    assignments: int
    outcomes: int
    successes: int
    conversion_rate: float
    conversion_interval: tuple[float, float]
    revenue_per_assignment: float
    cost_per_outcome: float
    error_rate: float
    complaint_rate: float


@dataclass(frozen=True)
class LiveCanaryStatistics:
    control: ArmStatistics
    candidate: ArmStatistics
    sample_ratio_z: float
    conversion_difference_lower_bound: float


def _metric(
    metrics: dict[str, object],
    mature_key: str,
    fallback_key: str,
) -> object:
    return metrics[mature_key] if mature_key in metrics else metrics.get(fallback_key, 0)


def _arm(metrics: dict[str, object], prefix: str) -> ArmStatistics:
    assignments = int(
        _metric(
            metrics,
            f"mature_{prefix}_assignments",
            f"{prefix}_assignments",
        )
        or 0
    )
    outcomes = int(
        _metric(
            metrics,
            f"mature_{prefix}_outcomes",
            f"{prefix}_outcomes",
        )
        or 0
    )
    successes = int(
        _metric(
            metrics,
            f"mature_{prefix}_successes",
            f"{prefix}_successes",
        )
        or 0
    )
    executions = int(metrics.get(f"{prefix}_executions", 0) or 0)
    errors = int(metrics.get(f"{prefix}_errors", 0) or 0)
    complaints = int(metrics.get(f"{prefix}_complaints", 0) or 0)
    revenue = _finite(
        _metric(
            metrics,
            f"mature_{prefix}_revenue",
            f"{prefix}_revenue",
        )
    )
    cost = _finite(
        _metric(
            metrics,
            f"mature_{prefix}_cost",
            f"{prefix}_cost",
        )
    )
    return ArmStatistics(
        assignments=assignments,
        outcomes=outcomes,
        successes=successes,
        conversion_rate=successes / assignments if assignments else 0.0,
        conversion_interval=wilson_interval(successes, assignments),
        revenue_per_assignment=revenue / assignments if assignments else 0.0,
        cost_per_outcome=(
            cost / successes
            if successes
            else float("inf") if cost else 0.0
        ),
        error_rate=errors / executions if executions else 0.0,
        complaint_rate=complaints / executions if executions else 0.0,
    )


def summarize(
    metrics: dict[str, object],
    expected_candidate_fraction: float,
) -> LiveCanaryStatistics:
    control = _arm(metrics, "control")
    candidate = _arm(metrics, "candidate")
    control_all = int(metrics.get("control_assignments", 0) or 0)
    candidate_all = int(metrics.get("candidate_assignments", 0) or 0)
    return LiveCanaryStatistics(
        control=control,
        candidate=candidate,
        sample_ratio_z=sample_ratio_z(
            candidate_all,
            control_all + candidate_all,
            expected_candidate_fraction,
        ),
        conversion_difference_lower_bound=difference_lower_bound(
            candidate.successes,
            candidate.assignments,
            control.successes,
            control.assignments,
        ),
    )


__all__ = [
    "ArmStatistics",
    "LiveCanaryStatistics",
    "difference_lower_bound",
    "sample_ratio_z",
    "summarize",
    "wilson_interval",
]
