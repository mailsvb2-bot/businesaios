from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class RolloutGuardPolicy:
    hard_stop_error_rate: float = 0.20
    staged_error_rate: float = 0.05
    staged_rollout_pct: int = 10
    full_rollout_pct: int = 100
    stop_rollout_pct: int = 0
