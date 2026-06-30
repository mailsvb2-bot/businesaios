from __future__ import annotations

from runtime.simulation import ScenarioOutcome, explain_scenario_outcome

CANON_THIN_HANDLER = True

def handle_simulation_explain(outcome: ScenarioOutcome) -> str:
    return explain_scenario_outcome(outcome)
