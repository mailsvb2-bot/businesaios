"""Auto-rollback guard.

Pure function: if metrics indicate collapse, suggest rollback.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RollbackMetrics:
    conversion_drop: float = 0.0


def should_rollback(metrics: RollbackMetrics) -> bool:
    return float(metrics.conversion_drop) > 0.3
