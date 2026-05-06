from __future__ import annotations

from core.product.types import EvaluationResult, FeatureRecord


class RetentionImpactEvaluator:
    def evaluate(self, feature: FeatureRecord) -> EvaluationResult:
        return EvaluationResult(
            name="retention_impact",
            value=feature.retention_delta,
            details={"retention_delta": feature.retention_delta},
        )
