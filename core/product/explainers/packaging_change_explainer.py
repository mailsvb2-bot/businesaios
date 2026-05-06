from __future__ import annotations

from core.product.types import PackagingProposal


class PackagingChangeExplainer:
    def explain(self, proposal: PackagingProposal) -> list[str]:
        return [f"{change.change_type.value}:{change.target}:{change.from_value}->{change.to_value} because {change.rationale}" for change in proposal.changes]
