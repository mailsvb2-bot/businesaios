from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class RetentionPricingFlowPolicy:
    rl_enabled_default: int = 0
    rl_lookback_days: int = 30
    rl_window_hours: int = 24
    rl_grid_radius_pct: float = 0.20
    rl_grid_step_rub: int = 100
    rl_min_price_rub: int = 100
    rl_max_price_rub: int = 999_999
    stoploss_enabled_default: int = 0
    stoploss_lookback_hours: int = 24
    stoploss_min_trials: int = 20
    stoploss_max_conv_drop_pct: float = 0.20
    stoploss_max_rev_drop_pct: float = 0.20
    stoploss_cooldown_hours: int = 6


DEFAULT_RETENTION_PRICING_FLOW_POLICY = RetentionPricingFlowPolicy()
