from __future__ import annotations

from ..contracts import ScenarioOutcome


def explain_scenario_outcome(outcome: ScenarioOutcome) -> str:
    return (
        f"scenario={outcome.scenario_name}; "
        f"confidence={outcome.confidence}; "
        f"downside_risk={outcome.downside_risk}"
    )
