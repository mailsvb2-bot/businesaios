from __future__ import annotations

from dataclasses import dataclass

from core.product.enums import ProposalMode, ProposalStatus, RoadmapBucket

PRODUCT_MODULE_ISSUER = "product-module"


@dataclass(frozen=True)
class RoadmapCapacity:
    max_now_items: int
    max_next_items: int
    max_later_items: int


@dataclass(frozen=True)
class RoadmapItem:
    feature_id: str
    bucket: RoadmapBucket
    priority_rank: int
    rationale: str


@dataclass(frozen=True)
class RoadmapProposal:
    proposal_id: str
    product_id: str
    items: list[RoadmapItem]
    status: ProposalStatus = ProposalStatus.DRAFT
    issuer_id: str = PRODUCT_MODULE_ISSUER
    mode: ProposalMode = ProposalMode.ADVISORY
    executable: bool = False

    @property
    def feature_id(self) -> str:
        """Convenience for single-feature proposals (e.g. handler smoke)."""
        return self.items[0].feature_id if self.items else ""
