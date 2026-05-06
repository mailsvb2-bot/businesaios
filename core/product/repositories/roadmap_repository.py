from __future__ import annotations

from core.product.types import RoadmapProposal


class RoadmapRepository:
    def __init__(self) -> None:
        self._items: dict[str, RoadmapProposal] = {}

    def save(self, proposal: RoadmapProposal) -> None:
        self._items[proposal.proposal_id] = proposal

    def get(self, proposal_id: str) -> RoadmapProposal | None:
        return self._items.get(proposal_id)
