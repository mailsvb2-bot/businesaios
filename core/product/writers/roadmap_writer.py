from __future__ import annotations

from core.product.types import RoadmapProposal


class InMemoryRoadmapWriter:
    def __init__(self) -> None:
        self._proposals: list[RoadmapProposal] = []

    def write_roadmap_proposal(self, proposal: RoadmapProposal) -> None:
        self._proposals.append(proposal)

    def list_proposals(self) -> list[RoadmapProposal]:
        return list(self._proposals)
