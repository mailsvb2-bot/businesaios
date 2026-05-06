from __future__ import annotations

from dataclasses import dataclass

from core.experiments.enums import RiskLevel, RolloutDecision


@dataclass(frozen=True)
class ExperimentEvaluated:
    experiment_id: str
    uplift: float
    p_value: float
    significant: bool
    risk_level: RiskLevel
    rollout_decision: RolloutDecision
