from __future__ import annotations

CANON_THIN_HANDLER = True

from runtime.product import RoadmapPriorityExplainer, RoadmapProposal


def handle_product_explain(proposal: RoadmapProposal) -> str:
    lines = RoadmapPriorityExplainer().explain(proposal, scores=[])
    if lines:
        return "\n".join(lines)
    return f"roadmap={proposal.proposal_id} items={len(proposal.items)}"
