from __future__ import annotations

from core.product.guards.capacity_data_guard import CapacityDataGuard
from core.product.guards.feature_data_guard import FeatureDataGuard
from core.product.guards.packaging_structure_guard import PackagingStructureGuard
from core.product.guards.proposal_boundary_guard import ProposalBoundaryGuard
from core.product.guards.roadmap_capacity_guard import RoadmapCapacityGuard
from core.product.guards.tier_overlap_guard import TierOverlapGuard
from core.product.types import GuardVerdict, FeatureRecord, PackagingProposal, RoadmapCapacity, RoadmapProposal


class ProductGuard:
    def __init__(
        self,
        feature_data_guard: FeatureDataGuard | None = None,
        capacity_data_guard: CapacityDataGuard | None = None,
        roadmap_capacity_guard: RoadmapCapacityGuard | None = None,
        packaging_structure_guard: PackagingStructureGuard | None = None,
        tier_overlap_guard: TierOverlapGuard | None = None,
        proposal_boundary_guard: ProposalBoundaryGuard | None = None,
    ) -> None:
        self._feature_data_guard = feature_data_guard or FeatureDataGuard()
        self._capacity_data_guard = capacity_data_guard or CapacityDataGuard()
        self._roadmap_capacity_guard = roadmap_capacity_guard or RoadmapCapacityGuard()
        self._packaging_structure_guard = packaging_structure_guard or PackagingStructureGuard()
        self._tier_overlap_guard = tier_overlap_guard or TierOverlapGuard()
        self._proposal_boundary_guard = proposal_boundary_guard or ProposalBoundaryGuard()

    def check_feature_data(self, features: list[FeatureRecord]) -> list[GuardVerdict]:
        return self._feature_data_guard.check_many(features)

    def check_capacity_data(self, capacity: RoadmapCapacity) -> list[GuardVerdict]:
        return [self._capacity_data_guard.check(capacity)]

    def check_roadmap(self, proposal: RoadmapProposal, capacity: RoadmapCapacity) -> list[GuardVerdict]:
        return [self._proposal_boundary_guard.check(proposal), self._roadmap_capacity_guard.check(proposal, capacity)]

    def check_packaging(self, proposal: PackagingProposal) -> list[GuardVerdict]:
        return [
            self._proposal_boundary_guard.check(proposal),
            self._packaging_structure_guard.check(proposal),
            self._tier_overlap_guard.check(proposal),
        ]
