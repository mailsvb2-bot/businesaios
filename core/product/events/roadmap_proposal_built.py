from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoadmapProposalBuilt:
    proposal_id: str
    product_id: str
    item_count: int
