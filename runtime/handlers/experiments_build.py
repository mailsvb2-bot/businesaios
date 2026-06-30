from __future__ import annotations

from runtime.experiments import Experiment, build_experiment

CANON_THIN_HANDLER = True

def handle_experiments_build(experiment_id: str, hypothesis: str, traffic_share: float) -> Experiment:
    return build_experiment(experiment_id=experiment_id, hypothesis=hypothesis, traffic_share=traffic_share)
