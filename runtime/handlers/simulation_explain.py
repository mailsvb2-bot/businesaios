from __future__ import annotations
CANON_THIN_HANDLER = True
from runtime.simulation import ScenarioOutcome, explain_scenario_outcome

def handle_simulation_explain(outcome: ScenarioOutcome) -> str:
    return explain_scenario_outcome(outcome)
