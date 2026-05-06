from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyticsMaterializationPolicy:
    default_window_days: int = 30
    snapshot_retention_days: int = 90
    alert_on_warning: bool = False
    alert_on_critical: bool = True
    retention_floor: float = 0.15
    execution_ratio_floor: float = 0.70
    blocked_ratio_ceiling: float = 0.20
    latency_p95_ceiling_ms: int = 3000
