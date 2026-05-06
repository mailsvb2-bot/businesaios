from __future__ import annotations

from core.product.builders.feature_score_builder import FeatureScoreBuilder
from core.product.enums import FeatureStatus
from core.product.policies.roadmap_priority_policy import RoadmapPriorityPolicy
from core.product.types import FeatureRecord, FeatureScore, RoadmapCapacity, RoadmapProposal

ELIGIBLE_ROADMAP_STATUSES = {
    FeatureStatus.DISCOVERY,
    FeatureStatus.READY,
    FeatureStatus.IN_PROGRESS,
    FeatureStatus.RELEASED,
}


class RoadmapProposalBuilder:
    def __init__(
        self,
        feature_score_builder: FeatureScoreBuilder | None = None,
        roadmap_priority_policy: RoadmapPriorityPolicy | None = None,
    ) -> None:
        self._feature_score_builder = feature_score_builder or FeatureScoreBuilder()
        self._roadmap_priority_policy = roadmap_priority_policy or RoadmapPriorityPolicy()

    def build(
        self,
        proposal_id: str,
        product_id: str,
        features: list[FeatureRecord],
        capacity: RoadmapCapacity,
    ) -> tuple[RoadmapProposal, list[FeatureScore]]:
        eligible = [feature for feature in features if feature.status in ELIGIBLE_ROADMAP_STATUSES]
        scores = [self._feature_score_builder.build(feature) for feature in eligible]
        items = self._roadmap_priority_policy.assign(scores=scores, capacity=capacity)
        proposal = RoadmapProposal(proposal_id=proposal_id, product_id=product_id, items=items)
        return proposal, scores
