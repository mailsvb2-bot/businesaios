from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True
@dataclass(frozen=True)
class StagedRolloutPolicy:
    default_error_rate: float = 0.0; fallback_error_rate: float = 1.0
    max_error_rate_for_promotion: float = 0.05; min_shadow_decisions: int = 1000
    min_production_outcomes: int = 100; min_outcome_observations: int = 100
    max_disagreement_rate: float = 0.50; max_critical_violations: int = 0
    max_average_cost_increase: float = 0.0; max_average_regret: float = 0.0
    max_p95_latency_ms: float = 500.0
DEFAULT_STAGED_ROLLOUT_POLICY = StagedRolloutPolicy()
