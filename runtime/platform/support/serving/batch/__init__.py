from __future__ import annotations

"""Canonical batch serving surface with compat alias submodules."""

from typing import Any


class BatchScoringJob:
    def run(self, handler, runtime, payloads: list[dict]) -> list[dict]:
        return [handler.handle(runtime, payload) for payload in payloads]

def run_bulk_action(payloads: list[dict[str, Any]]) -> dict[str, int]:
    return {"processed": len(payloads)}

class EvaluationJob:
    def run(self, evaluator, candidate_id: str, payloads):
        return [evaluator.evaluate(candidate_id, payload) for payload in payloads]

class OfflineInferenceJob:
    def run(self, runtime, observations):
        return [runtime.predict(observation) for observation in observations]

class ReplayScoringJob:
    def run(self, scorer, replay_samples):
        return [scorer(sample) for sample in replay_samples]

__all__ = [
    "BatchScoringJob",
    "EvaluationJob",
    "OfflineInferenceJob",
    "ReplayScoringJob",
    "run_bulk_action",
]
