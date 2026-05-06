from __future__ import annotations

from core.product.types import EvaluationResult, FeatureRecord


class ComplexityEvaluator:
    def evaluate(self, feature: FeatureRecord) -> EvaluationResult:
        return EvaluationResult(
            name="complexity",
            value=feature.effort_points,
            details={"effort_points": feature.effort_points},
        )
