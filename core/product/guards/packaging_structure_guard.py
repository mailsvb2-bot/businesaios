from __future__ import annotations

from core.product.types import GuardVerdict, PackagingProposal


class PackagingStructureGuard:
    def check(self, proposal: PackagingProposal) -> GuardVerdict:
        if not proposal.tier_structure:
            return GuardVerdict(False, "empty_tier_structure", "Packaging proposal has no tier structure")
        tier_names = [tier.tier_name for tier in proposal.tier_structure]
        if len(tier_names) != len(set(tier_names)):
            return GuardVerdict(False, "duplicate_tier_name", "Packaging proposal contains duplicate tier names")
        required_tiers = {"starter", "growth", "premium"}
        if not required_tiers.issubset(set(tier_names)):
            return GuardVerdict(False, "missing_required_tiers", "Packaging proposal must contain starter, growth and premium tiers")
        non_empty_tiers = sum(1 for tier in proposal.tier_structure if tier.included_features)
        if non_empty_tiers < 2:
            return GuardVerdict(False, "tier_distribution_too_sparse", "Packaging proposal collapses distribution into too few tiers")
        return GuardVerdict(True, "ok", "Packaging structure passes safety checks")
