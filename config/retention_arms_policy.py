from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class RetentionArmsPolicy:
    bandit_lookback_days: int = 30
    bandit_window_ms_per_hour: int = 3600 * 1000
    millis_per_day: int = 86400 * 1000
    default_candidate_weight: float = 1.0
    fallback_arm: str = "NONE"
    offer_30_arm: str = "offer_30_14900"
    offer_bundle_arm: str = "offer_bundle_14_30"
    offer_90_arm: str = "offer_90_21900"
    selection_score_floor: float = -1.0


DEFAULT_RETENTION_ARMS_POLICY = RetentionArmsPolicy()
