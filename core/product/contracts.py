from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from core.product.types import (
    FeatureRecord,
    FeatureScore,
    PackagingProposal,
    RoadmapCapacity,
    RoadmapProposal,
)
from core.product.types import (
    ProductFeature as ProductFeature,
)


class FeatureReader(Protocol):
    def read_features(self, product_id: str) -> Sequence[FeatureRecord]: ...


class RoadmapReader(Protocol):
    def read_capacity(self, product_id: str) -> RoadmapCapacity: ...


class FeatureWriter(Protocol):
    def write_feature_score(self, product_id: str, score: FeatureScore) -> None: ...


class RoadmapWriter(Protocol):
    def write_roadmap_proposal(self, proposal: RoadmapProposal) -> None: ...


class PackagingWriter(Protocol):
    def write_packaging_proposal(self, proposal: PackagingProposal) -> None: ...


class FeatureRepositoryContract(Protocol):
    def save(self, product_id: str, feature: FeatureRecord) -> None: ...
    def list_by_product(self, product_id: str) -> list[FeatureRecord]: ...


class RoadmapRepositoryContract(Protocol):
    def save(self, proposal: RoadmapProposal) -> None: ...
    def get(self, proposal_id: str) -> RoadmapProposal | None: ...


class PackagingRepositoryContract(Protocol):
    def save(self, proposal: PackagingProposal) -> None: ...
    def get(self, proposal_id: str) -> PackagingProposal | None: ...
