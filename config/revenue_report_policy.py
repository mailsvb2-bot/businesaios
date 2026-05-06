from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class RevenueReportPolicy:
    latest_events_limit: int = 20000
    minimum_impressions_for_autopilot: int = 50
    ctr_threshold: float = 0.02
    cr_threshold: float = 0.05
    uplift_percent_multiplier: float = 100.0
    default_action_key: str = "double_winner"
    increase_impressions_action_key: str = "increase_impressions"
    improve_ctr_action_key: str = "improve_ctr"
    improve_cr_action_key: str = "improve_cr"


DEFAULT_REVENUE_REPORT_POLICY = RevenueReportPolicy()
