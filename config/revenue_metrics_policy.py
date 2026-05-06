from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class RevenueMetricsPolicy:
    latest_events_limit: int = 20000
    epoch_millis_threshold: float = 2_000_000_000_000.0
    window_days: int = 1
    zero_amount: float = 0.0
    ctr_zero: float = 0.0
    cr_zero: float = 0.0
    arpu_zero: float = 0.0


DEFAULT_REVENUE_METRICS_POLICY = RevenueMetricsPolicy()
