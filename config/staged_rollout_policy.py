from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True


@dataclass(frozen=True)
class StagedRolloutPolicy:
    default_error_rate: float = 0.0
    fallback_error_rate: float = 1.0
    max_error_rate_for_promotion: float = 0.05


DEFAULT_STAGED_ROLLOUT_POLICY = StagedRolloutPolicy()
