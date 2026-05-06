from __future__ import annotations

from typing import Any, Dict

from .contracts import ScenarioInput, ScenarioOutcome, SimScore
from .evaluators.downside_risk_evaluator import evaluate_downside_risk
from .evaluators.step_score_evaluator import evaluate_step_score


def simulate_scenario(scenario: ScenarioInput) -> ScenarioOutcome:
    return ScenarioOutcome(
        tenant_id=scenario.tenant_id,
        scenario_name=scenario.scenario_name,
        confidence=0.0,
        downside_risk=0.0,
    )


def score_step(*, action: str, payload: Dict[str, Any], snapshot: Dict[str, Any]) -> SimScore:
    return evaluate_step_score(action=action, payload=payload, snapshot=snapshot)
