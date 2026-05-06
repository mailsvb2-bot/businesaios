from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfitMetricsPolicy:
    revenue_events_limit: int = 20000
    ads_metrics_limit: int = 5000
    minor_units_multiplier: float = 100.0


DEFAULT_PROFIT_METRICS_POLICY = ProfitMetricsPolicy()
