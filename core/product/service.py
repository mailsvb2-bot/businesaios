from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from core.product.builders.packaging_proposal_builder import PackagingProposalBuilder
from core.product.builders.roadmap_proposal_builder import RoadmapProposalBuilder
from core.product.enums import ProposalStatus, RoadmapBucket
from core.product.errors import MissingProductDataError, ProductValidationError
from core.product.events.packaging_guard_triggered import PackagingGuardTriggered
from core.product.events.roadmap_guard_triggered import RoadmapGuardTriggered
from core.product.events.roadmap_proposal_built import RoadmapProposalBuilt
from core.product.guard import ProductGuard
from core.product.projections.feature_priority_projection import FeaturePriorityProjection
from core.product.projections.roadmap_projection import RoadmapProjection
from core.product.types import (
    FeatureRecord,
    FeatureScore,
    PackagingProposal,
    ProductFeature,
    RoadmapCapacity,
    RoadmapItem,
    RoadmapProposal,
)

PRODUCT_MODULE_ISSUER = "product-module"


def build_roadmap_proposal(feature: ProductFeature) -> RoadmapProposal:
    """Build a minimal roadmap proposal from a single feature (handler/smoke use)."""
    item = RoadmapItem(
        feature_id=feature.feature_id,
        bucket=RoadmapBucket.NOW,
        priority_rank=1,
        rationale=feature.name or "smoke",
    )
    return RoadmapProposal(
        proposal_id=f"roadmap-{uuid4().hex}",
        product_id="",
        items=[item],
        status=ProposalStatus.DRAFT,
        issuer_id=PRODUCT_MODULE_ISSUER,
    )


class ProductService:
    def __init__(
        self,
        feature_reader,
        roadmap_reader,
        feature_writer,
        roadmap_writer,
        packaging_writer,
        roadmap_repository,
        packaging_repository,
        roadmap_proposal_builder: RoadmapProposalBuilder | None = None,
        packaging_proposal_builder: PackagingProposalBuilder | None = None,
        product_guard: ProductGuard | None = None,
        roadmap_projection: RoadmapProjection | None = None,
        feature_priority_projection: FeaturePriorityProjection | None = None,
    ) -> None:
        self._feature_reader = feature_reader
        self._roadmap_reader = roadmap_reader
        self._feature_writer = feature_writer
        self._roadmap_writer = roadmap_writer
        self._packaging_writer = packaging_writer
        self._roadmap_repository = roadmap_repository
        self._packaging_repository = packaging_repository
        self._roadmap_proposal_builder = roadmap_proposal_builder or RoadmapProposalBuilder()
        self._packaging_proposal_builder = packaging_proposal_builder or PackagingProposalBuilder()
        self._product_guard = product_guard or ProductGuard()
        self._roadmap_projection = roadmap_projection or RoadmapProjection()
        self._feature_priority_projection = feature_priority_projection or FeaturePriorityProjection()

    def build_roadmap_proposal(self, product_id: str) -> tuple[RoadmapProposal, dict[str, object], list[object]]:
        features = self._load_features(product_id)
        capacity = self._load_capacity(product_id)
        proposal, scores = self._roadmap_proposal_builder.build(
            proposal_id=f"roadmap-{uuid4().hex}",
            product_id=product_id,
            features=features,
            capacity=capacity,
        )
        self._write_scores(product_id, scores)
        guarded_proposal, guard_events = self._guard_roadmap(proposal, capacity)
        self._roadmap_writer.write_roadmap_proposal(guarded_proposal)
        self._roadmap_repository.save(guarded_proposal)
        projection = {
            "roadmap": self._roadmap_projection.project(guarded_proposal),
            "feature_priorities": self._feature_priority_projection.project(scores),
        }
        events: list[object] = [RoadmapProposalBuilt(proposal_id=guarded_proposal.proposal_id, product_id=guarded_proposal.product_id, item_count=len(guarded_proposal.items))]
        events.extend(guard_events)
        return guarded_proposal, projection, events

    def build_packaging_proposal(self, product_id: str) -> tuple[PackagingProposal, list[PackagingGuardTriggered]]:
        features = self._load_features(product_id)
        proposal = self._packaging_proposal_builder.build(
            proposal_id=f"packaging-{uuid4().hex}",
            product_id=product_id,
            features=features,
        )
        guarded_proposal, guard_events = self._guard_packaging(proposal)
        self._packaging_writer.write_packaging_proposal(guarded_proposal)
        self._packaging_repository.save(guarded_proposal)
        return guarded_proposal, guard_events

    def _load_features(self, product_id: str) -> list[FeatureRecord]:
        features = list(self._feature_reader.read_features(product_id))
        if not features:
            raise MissingProductDataError(f"no features found for product_id={product_id}")
        failures = [v for v in self._product_guard.check_feature_data(features) if not v.allowed]
        if failures:
            raise ProductValidationError('; '.join(v.message for v in failures))
        return features

    def _load_capacity(self, product_id: str) -> RoadmapCapacity:
        capacity = self._roadmap_reader.read_capacity(product_id)
        failures = [v for v in self._product_guard.check_capacity_data(capacity) if not v.allowed]
        if failures:
            raise ProductValidationError('; '.join(v.message for v in failures))
        return capacity

    def _write_scores(self, product_id: str, scores: list[FeatureScore]) -> None:
        for score in scores:
            self._feature_writer.write_feature_score(product_id, score)

    def _guard_roadmap(self, proposal: RoadmapProposal, capacity: RoadmapCapacity) -> tuple[RoadmapProposal, list[RoadmapGuardTriggered]]:
        failed = [v for v in self._product_guard.check_roadmap(proposal, capacity) if not v.allowed]
        if not failed:
            return proposal, []
        blocked = replace(proposal, status=ProposalStatus.BLOCKED)
        events = [RoadmapGuardTriggered(proposal_id=blocked.proposal_id, product_id=blocked.product_id, guard_code=v.code, message=v.message) for v in failed]
        return blocked, events

    def _guard_packaging(self, proposal: PackagingProposal) -> tuple[PackagingProposal, list[PackagingGuardTriggered]]:
        failed = [v for v in self._product_guard.check_packaging(proposal) if not v.allowed]
        if not failed:
            return proposal, []
        blocked = replace(proposal, status=ProposalStatus.BLOCKED)
        events = [PackagingGuardTriggered(proposal_id=blocked.proposal_id, product_id=blocked.product_id, guard_code=v.code, message=v.message) for v in failed]
        return blocked, events
