from __future__ import annotations

from itertools import combinations

from core.product.types import GuardVerdict, PackagingProposal


class TierOverlapGuard:
    def check(self, proposal: PackagingProposal) -> GuardVerdict:
        features_by_tier = {tier.tier_name: set(tier.included_features) for tier in proposal.tier_structure}
        for left_name, right_name in combinations(sorted(features_by_tier.keys()), 2):
            overlap = features_by_tier[left_name].intersection(features_by_tier[right_name])
            if overlap:
                return GuardVerdict(False, "tier_feature_overlap", f"Features appear in both {left_name} and {right_name}: {sorted(overlap)}")
        return GuardVerdict(True, "ok", "No tier overlap detected")
