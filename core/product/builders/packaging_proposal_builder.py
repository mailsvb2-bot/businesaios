from __future__ import annotations

from core.product.builders.tier_structure_builder import TierStructureBuilder
from core.product.policies.packaging_policy import PackagingPolicy
from core.product.types import FeatureRecord, PackagingProposal


class PackagingProposalBuilder:
    def __init__(
        self,
        packaging_policy: PackagingPolicy | None = None,
        tier_structure_builder: TierStructureBuilder | None = None,
    ) -> None:
        self._packaging_policy = packaging_policy or PackagingPolicy()
        self._tier_structure_builder = tier_structure_builder or TierStructureBuilder()

    def build(self, proposal_id: str, product_id: str, features: list[FeatureRecord]) -> PackagingProposal:
        changes = self._packaging_policy.propose_changes(features)
        tier_structure = self._tier_structure_builder.build(features)
        return PackagingProposal(
            proposal_id=proposal_id,
            product_id=product_id,
            changes=changes,
            tier_structure=tier_structure,
        )
