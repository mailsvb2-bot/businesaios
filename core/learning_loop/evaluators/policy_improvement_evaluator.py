from __future__ import annotations

from ..contracts import PolicyUpdateProposal


def evaluate_policy_improvement(proposal: PolicyUpdateProposal) -> float:
    return proposal.confidence
