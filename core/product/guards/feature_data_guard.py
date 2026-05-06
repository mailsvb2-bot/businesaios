from __future__ import annotations

import math

from core.product.types import FeatureRecord, GuardVerdict


class FeatureDataGuard:
    def check_many(self, features: list[FeatureRecord]) -> list[GuardVerdict]:
        if not features:
            return [GuardVerdict(False, "empty_feature_collection", "Feature collection is empty")]
        seen_ids: set[str] = set()
        verdicts: list[GuardVerdict] = []
        for feature in features:
            verdicts.extend(self._check_single(feature))
            if feature.feature_id in seen_ids:
                verdicts.append(GuardVerdict(False, "duplicate_feature_id", f"Duplicate feature_id: {feature.feature_id}"))
            seen_ids.add(feature.feature_id)
        return verdicts

    def _check_single(self, feature: FeatureRecord) -> list[GuardVerdict]:
        verdicts: list[GuardVerdict] = []
        if not feature.feature_id.strip():
            verdicts.append(GuardVerdict(False, "empty_feature_id", "feature_id must not be empty"))
        if not feature.name.strip():
            verdicts.append(GuardVerdict(False, "empty_feature_name", "feature name must not be empty"))
        numeric_fields = {
            "adoption_rate": feature.adoption_rate,
            "retention_delta": feature.retention_delta,
            "revenue_delta": feature.revenue_delta,
            "effort_points": feature.effort_points,
            "risk_score": feature.risk_score,
        }
        for name, value in numeric_fields.items():
            if not math.isfinite(value):
                verdicts.append(GuardVerdict(False, "non_finite_feature_metric", f"{feature.feature_id}.{name} is not finite"))
        if feature.adoption_rate < 0.0 or feature.adoption_rate > 1.0:
            verdicts.append(GuardVerdict(False, "invalid_adoption_rate", f"{feature.feature_id}.adoption_rate must be between 0 and 1"))
        if feature.effort_points < 0.0:
            verdicts.append(GuardVerdict(False, "negative_effort_points", f"{feature.feature_id}.effort_points must be >= 0"))
        if feature.risk_score < 0.0:
            verdicts.append(GuardVerdict(False, "negative_risk_score", f"{feature.feature_id}.risk_score must be >= 0"))
        return verdicts
