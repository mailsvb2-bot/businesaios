from __future__ import annotations

CANON_THIN_HANDLER = True
from runtime.learning_loop import PolicyUpdateProposal, explain_policy_update


def handle_learning_loop_explain(proposal: PolicyUpdateProposal) -> str:
    return explain_policy_update(proposal)
