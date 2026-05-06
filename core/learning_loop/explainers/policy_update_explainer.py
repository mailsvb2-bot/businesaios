from __future__ import annotations

from ..contracts import PolicyUpdateProposal


def explain_policy_update(proposal: PolicyUpdateProposal) -> str:
    return (
        f"policy_name={proposal.policy_name}; "
        f"reason={proposal.reason}; "
        f"confidence={proposal.confidence}"
    )
