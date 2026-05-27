from __future__ import annotations

"""Canonical domain evaluation surface with compat alias submodules."""

from runtime.platform.support.contracts.evaluation import EvaluationResult


class BusinessKPIEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        kpi = float(payload.get("business_kpi", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"business_kpi": kpi})

class CalibrationEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        calibration = float(payload.get("calibration", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"calibration": calibration})

class CostEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        cost = float(payload.get("cost", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"cost": cost})

class DriftEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        drift = float(payload.get("drift", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"drift": drift})

class FairnessEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        fairness = float(payload.get("fairness", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"fairness": fairness})

class LatencyEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        latency = float(payload.get("latency_ms", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"latency_ms": latency})

class StabilityEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        stability = float(payload.get("stability", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"stability": stability})

_ALIAS_EXPORTS = {
    "business_kpi_eval": "BusinessKPIEval",
    "calibration_eval": "CalibrationEval",
    "cost_eval": "CostEval",
    "drift_eval": "DriftEval",
    "fairness_eval": "FairnessEval",
    "latency_eval": "LatencyEval",
    "stability_eval": "StabilityEval",
}

__all__ = [
    "BusinessKPIEval",
    "CalibrationEval",
    "CostEval",
    "DriftEval",
    "FairnessEval",
    "LatencyEval",
    "StabilityEval",
] + list(_ALIAS_EXPORTS)
