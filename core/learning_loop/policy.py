from __future__ import annotations

from .contracts import PolicyUpdateProposal


def is_promotion_allowed(proposal: PolicyUpdateProposal) -> bool:
    return proposal.confidence >= 0.8
