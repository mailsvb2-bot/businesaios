from __future__ import annotations

from core.product.evaluators.complexity_evaluator import ComplexityEvaluator
from core.product.evaluators.feature_impact_evaluator import FeatureImpactEvaluator
from core.product.evaluators.retention_impact_evaluator import RetentionImpactEvaluator
from core.product.evaluators.roadmap_risk_evaluator import RoadmapRiskEvaluator
from core.product.types import FeatureRecord, FeatureScore


class FeatureScoreBuilder:
    def __init__(
        self,
        impact_evaluator: FeatureImpactEvaluator | None = None,
        retention_evaluator: RetentionImpactEvaluator | None = None,
        complexity_evaluator: ComplexityEvaluator | None = None,
        risk_evaluator: RoadmapRiskEvaluator | None = None,
    ) -> None:
        self._impact_evaluator = impact_evaluator or FeatureImpactEvaluator()
        self._retention_evaluator = retention_evaluator or RetentionImpactEvaluator()
        self._complexity_evaluator = complexity_evaluator or ComplexityEvaluator()
        self._risk_evaluator = risk_evaluator or RoadmapRiskEvaluator()

    def build(self, feature: FeatureRecord) -> FeatureScore:
        value_score = self._impact_evaluator.evaluate(feature).value
        retention_score = self._retention_evaluator.evaluate(feature).value
        complexity_score = self._complexity_evaluator.evaluate(feature).value
        risk_score = self._risk_evaluator.evaluate(feature).value
        total_score = value_score + retention_score - (complexity_score * 0.50) - (risk_score * 0.75)
        return FeatureScore(
            feature_id=feature.feature_id,
            value_score=value_score,
            retention_score=retention_score,
            complexity_score=complexity_score,
            risk_score=risk_score,
            total_score=total_score,
        )
