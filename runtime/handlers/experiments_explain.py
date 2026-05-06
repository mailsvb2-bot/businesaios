from __future__ import annotations

CANON_THIN_HANDLER = True

from runtime.experiments import ExperimentResult, explain_experiment_result


def handle_experiments_explain(result: ExperimentResult) -> str:
    return explain_experiment_result(result)
