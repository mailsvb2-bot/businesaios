from __future__ import annotations

from core.product.types import PackagingProposal


class InMemoryPackagingWriter:
    def __init__(self) -> None:
        self._proposals: list[PackagingProposal] = []

    def write_packaging_proposal(self, proposal: PackagingProposal) -> None:
        self._proposals.append(proposal)

    def list_proposals(self) -> list[PackagingProposal]:
        return list(self._proposals)
