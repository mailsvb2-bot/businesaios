from __future__ import annotations

from core.product.types import FeatureScore


class FeaturePriorityProjection:
    def project(self, scores: list[FeatureScore]) -> list[dict[str, float | str]]:
        ordered = sorted(scores, key=lambda item: (-item.total_score, item.feature_id))
        return [
            {
                "feature_id": score.feature_id,
                "total_score": score.total_score,
                "value_score": score.value_score,
                "retention_score": score.retention_score,
                "complexity_score": score.complexity_score,
                "risk_score": score.risk_score,
            }
            for score in ordered
        ]
