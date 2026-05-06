from __future__ import annotations

from dataclasses import dataclass, field

from config.risk_evaluation_policy import (
    DEFAULT_STOP_LOSS_DEFAULTS_POLICY,
    StopLossDefaultsPolicy,
)


def _stop_loss_defaults() -> StopLossDefaultsPolicy:
    return DEFAULT_STOP_LOSS_DEFAULTS_POLICY


@dataclass(frozen=True)
class StopLossConfig:
    enabled: bool = field(default_factory=lambda: bool(_stop_loss_defaults().enabled))
    lookback_hours: int = field(default_factory=lambda: int(_stop_loss_defaults().lookback_hours))
    min_trials: int = field(default_factory=lambda: int(_stop_loss_defaults().min_trials))
    cooldown_hours: int = field(default_factory=lambda: int(_stop_loss_defaults().cooldown_hours))
    cooldown_max_hours: int = field(default_factory=lambda: int(_stop_loss_defaults().cooldown_max_hours))
    cooldown_backoff_lookback_hours: int = field(default_factory=lambda: int(_stop_loss_defaults().cooldown_backoff_lookback_hours))
    cooldown_decay_enabled: bool = field(default_factory=lambda: bool(_stop_loss_defaults().cooldown_decay_enabled))
    max_conv_drop_pct: float = field(default_factory=lambda: float(_stop_loss_defaults().max_conv_drop_pct))
    max_rev_drop_pct: float = field(default_factory=lambda: float(_stop_loss_defaults().max_rev_drop_pct))
