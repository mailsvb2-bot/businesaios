from __future__ import annotations

from core.product.types import EvaluationResult, FeatureRecord


class FeatureImpactEvaluator:
    def evaluate(self, feature: FeatureRecord) -> EvaluationResult:
        value = (
            feature.adoption_rate * 0.40
            + feature.retention_delta * 0.35
            + feature.revenue_delta * 0.25
        )
        return EvaluationResult(
            name="feature_impact",
            value=value,
            details={
                "adoption_rate": feature.adoption_rate,
                "retention_delta": feature.retention_delta,
                "revenue_delta": feature.revenue_delta,
            },
        )
