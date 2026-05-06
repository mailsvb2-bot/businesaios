from __future__ import annotations

from ..contracts import ScenarioOutcome


def evaluate_downside_risk(outcome: ScenarioOutcome) -> float:
    return outcome.downside_risk
