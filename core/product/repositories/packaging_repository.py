from __future__ import annotations

from core.product.types import PackagingProposal


class PackagingRepository:
    def __init__(self) -> None:
        self._items: dict[str, PackagingProposal] = {}

    def save(self, proposal: PackagingProposal) -> None:
        self._items[proposal.proposal_id] = proposal

    def get(self, proposal_id: str) -> PackagingProposal | None:
        return self._items.get(proposal_id)
