from __future__ import annotations

from .contracts import ScenarioOutcome
from .errors import SimulationGuardViolation
from .evaluators.downside_risk_evaluator import evaluate_downside_risk


def require_safe_downside(outcome: ScenarioOutcome, maximum: float = 1.0) -> None:
    downside_risk = evaluate_downside_risk(outcome)
    if downside_risk > maximum:
        raise SimulationGuardViolation(
            f"Scenario downside risk {downside_risk} exceeds {maximum}."
        )
