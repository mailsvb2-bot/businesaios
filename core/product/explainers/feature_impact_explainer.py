from __future__ import annotations

from core.product.types import FeatureRecord


class FeatureImpactExplainer:
    def explain(self, feature: FeatureRecord) -> str:
        return (
            f"feature={feature.feature_id} adoption={feature.adoption_rate:.4f} retention_delta={feature.retention_delta:.4f} revenue_delta={feature.revenue_delta:.4f} effort={feature.effort_points:.4f} risk={feature.risk_score:.4f}"
        )
