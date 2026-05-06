from __future__ import annotations

from core.product.types import EvaluationResult, FeatureRecord


class RoadmapRiskEvaluator:
    def evaluate(self, feature: FeatureRecord) -> EvaluationResult:
        return EvaluationResult(
            name="roadmap_risk",
            value=feature.risk_score,
            details={"risk_score": feature.risk_score},
        )
