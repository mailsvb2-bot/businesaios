from __future__ import annotations

from runtime.product import RoadmapPriorityExplainer, RoadmapProposal

CANON_THIN_HANDLER = True

def handle_product_explain(proposal: RoadmapProposal) -> str:
    lines = RoadmapPriorityExplainer().explain(proposal, scores=[])
    if lines:
        return "\n".join(lines)
    return f"roadmap={proposal.proposal_id} items={len(proposal.items)}"
