from __future__ import annotations

from core.product.enums import FeatureStatus, PackagingChangeType
from core.product.types import FeatureRecord, PackagingChange


class PackagingPolicy:
    def propose_changes(self, features: list[FeatureRecord]) -> list[PackagingChange]:
        changes: list[PackagingChange] = []
        ordered = sorted(features, key=lambda item: item.feature_id)
        for feature in ordered:
            if feature.status == FeatureStatus.DEPRECATED:
                continue
            if feature.revenue_delta >= 0.15 and feature.adoption_rate >= 0.20:
                changes.append(
                    PackagingChange(
                        change_type=PackagingChangeType.TIER,
                        target=feature.feature_id,
                        from_value="growth",
                        to_value="premium",
                        rationale="high monetization leverage with established adoption",
                    )
                )
                continue
            if feature.adoption_rate < 0.05 and feature.effort_points >= 8:
                changes.append(
                    PackagingChange(
                        change_type=PackagingChangeType.BUNDLE,
                        target=feature.feature_id,
                        from_value="standalone",
                        to_value="bundle_only",
                        rationale="weak standalone adoption with high maintenance cost",
                    )
                )
        return changes
