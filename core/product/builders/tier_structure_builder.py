from __future__ import annotations

from collections.abc import Iterable

from core.product.enums import FeatureStatus
from core.product.types import FeatureRecord, TierDefinition


class TierStructureBuilder:
    def build(self, features: Iterable[FeatureRecord]) -> list[TierDefinition]:
        starter: list[str] = []
        growth: list[str] = []
        premium: list[str] = []
        ordered = sorted(features, key=lambda item: item.feature_id)
        for feature in ordered:
            if feature.status == FeatureStatus.DEPRECATED:
                continue
            if feature.adoption_rate >= 0.25 and feature.effort_points <= 5:
                starter.append(feature.feature_id)
                continue
            if feature.revenue_delta >= 0.10 or feature.effort_points >= 8:
                premium.append(feature.feature_id)
                continue
            growth.append(feature.feature_id)
        return [
            TierDefinition(tier_name="starter", included_features=starter),
            TierDefinition(tier_name="growth", included_features=growth),
            TierDefinition(tier_name="premium", included_features=premium),
        ]
