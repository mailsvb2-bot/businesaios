from __future__ import annotations

from runtime.experiments import ExperimentResult, explain_experiment_result

CANON_THIN_HANDLER = True

def handle_experiments_explain(result: ExperimentResult) -> str:
    return explain_experiment_result(result)
