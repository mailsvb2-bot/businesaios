from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class AdsRulesPolicy:
    min_conversions_for_scale: int = 3
    scale_step_pct: float = 7.0
    stop_loss_spend: float = 20.0
    stop_loss_budget_delta_pct: float = -10.0
    yesterday_days_offset: int = 1


DEFAULT_ADS_RULES_POLICY = AdsRulesPolicy()
