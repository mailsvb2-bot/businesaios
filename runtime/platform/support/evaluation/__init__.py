from __future__ import annotations

"""Canonical evaluation surface with compat alias submodules."""

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Protocol

from runtime.platform.support.contracts.evaluation import EvaluationResult

class BaselineComparator:
    def compare(self, baseline: float, candidate: float) -> dict[str, float]:
        return {
            "baseline": baseline,
            "candidate": candidate,
            "improvement": candidate - baseline,
        }

class BenchmarkRunner:
    def run(self, evaluator, candidate_id: str, benchmark_payloads) -> list:
        return [evaluator.evaluate(candidate_id, payload) for payload in benchmark_payloads]

class ConfidenceIntervals:
    def interval(self, mean: float, margin: float) -> tuple[float, float]:
        return mean - margin, mean + margin

class Evaluator(Protocol):
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        ...

class EvaluationRegistry:
    def __init__(self) -> None:
        self._items: Dict[str, EvaluationResult] = {}

    def register(self, result: EvaluationResult) -> None:
        self._items[result.candidate_id] = result

    def get(self, candidate_id: str) -> EvaluationResult:
        return self._items[candidate_id]

@dataclass(frozen=True)
class EvaluationRequest:
    candidate_id: str
    dataset_id: str

@dataclass(frozen=True)
class StoredEvaluationResult:
    candidate_id: str
    metrics: Mapping[str, float]

class EvaluationSuite:
    def __init__(self, evaluators) -> None:
        self._evaluators = list(evaluators)

    def run(self, candidate_id: str, payload) -> list:
        return [evaluator.evaluate(candidate_id, payload) for evaluator in self._evaluators]

class BasicEvaluator:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        metric = float(payload.get("score", 0.0)) if isinstance(payload, dict) else float(payload)
        return EvaluationResult(candidate_id=candidate_id, metrics={"score": metric})

class PolicyComparator:
    def better(self, left: float, right: float) -> bool:
        return left > right

class RegressionRunner:
    def run(self, baseline: float, current: float) -> dict[str, float]:
        return {"baseline": baseline, "current": current, "delta": current - baseline}

class ScoreAggregation:
    def aggregate(self, metrics: Iterable[Mapping[str, float]]) -> dict[str, float]:
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for metric_set in metrics:
            for name, value in metric_set.items():
                totals[name] = totals.get(name, 0.0) + value
                counts[name] = counts.get(name, 0) + 1
        return {name: totals[name] / counts[name] for name in totals}

class ScoreNormalization:
    def normalize(self, score: float, low: float = 0.0, high: float = 1.0) -> float:
        if high == low:
            return score
        return (score - low) / (high - low)

class SignificanceTesting:
    def significant(self, delta: float, threshold: float = 0.01) -> bool:
        return abs(delta) >= threshold

_ALIAS_EXPORTS = {
    "baseline_comparator": "BaselineComparator",
    "benchmark_runner": "BenchmarkRunner",
    "confidence_intervals": "ConfidenceIntervals",
    "contracts": "Evaluator",
    "evaluation_registry": "EvaluationRegistry",
    "evaluation_request": "EvaluationRequest",
    "evaluation_result": "StoredEvaluationResult",
    "evaluation_suite": "EvaluationSuite",
    "evaluator": "BasicEvaluator",
    "policy_comparator": "PolicyComparator",
    "regression_runner": "RegressionRunner",
    "score_aggregation": "ScoreAggregation",
    "score_normalization": "ScoreNormalization",
    "significance_testing": "SignificanceTesting",
}

__all__ = [
    "BaselineComparator",
    "BenchmarkRunner",
    "ConfidenceIntervals",
    "Evaluator",
    "EvaluationRegistry",
    "EvaluationRequest",
    "StoredEvaluationResult",
    "EvaluationSuite",
    "BasicEvaluator",
    "PolicyComparator",
    "RegressionRunner",
    "ScoreAggregation",
    "ScoreNormalization",
    "SignificanceTesting",
] + list(_ALIAS_EXPORTS)
