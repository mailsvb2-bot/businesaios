"""Canonical safety evaluation surface with compat alias submodules."""

from __future__ import annotations


from runtime.platform.support.contracts.evaluation import EvaluationResult


class AbuseCaseEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        score = float(payload.get("abuse_case_score", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"abuse_case_score": score})

class AdversarialEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        score = float(payload.get("adversarial_resilience", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"adversarial_resilience": score})

class AnomalySensitivityEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        score = float(payload.get("anomaly_sensitivity", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"anomaly_sensitivity": score})

class ConstraintViolationEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        count = float(payload.get("constraint_violations", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"constraint_violations": count})

class RareEventEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        score = float(payload.get("rare_event_score", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"rare_event_score": score})

class RobustnessEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        score = float(payload.get("robustness", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"robustness": score})

class TailRiskEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        risk = float(payload.get("tail_risk", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"tail_risk": risk})

class SafetyEvaluator:
    def __init__(
        self,
        tail_risk_eval: TailRiskEval | None = None,
        constraint_eval: ConstraintViolationEval | None = None,
    ) -> None:
        self._tail_risk_eval = tail_risk_eval or TailRiskEval()
        self._constraint_eval = constraint_eval or ConstraintViolationEval()

    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        tail = self._tail_risk_eval.evaluate(candidate_id, payload).metrics["tail_risk"]
        violations = self._constraint_eval.evaluate(candidate_id, payload).metrics["constraint_violations"]
        safety_score = max(0.0, 1.0 - tail - violations)
        return EvaluationResult(candidate_id=candidate_id, metrics={"safety_score": safety_score})

_ALIAS_EXPORTS = {
    "abuse_case_eval": "AbuseCaseEval",
    "adversarial_eval": "AdversarialEval",
    "anomaly_sensitivity_eval": "AnomalySensitivityEval",
    "constraint_violation_eval": "ConstraintViolationEval",
    "rare_event_eval": "RareEventEval",
    "robustness_eval": "RobustnessEval",
    "safety_evaluator": "SafetyEvaluator",
    "tail_risk_eval": "TailRiskEval",
}

__all__ = [
    "AbuseCaseEval",
    "AdversarialEval",
    "AnomalySensitivityEval",
    "ConstraintViolationEval",
    "RareEventEval",
    "RobustnessEval",
    "SafetyEvaluator",
    "TailRiskEval",
] + list(_ALIAS_EXPORTS)
