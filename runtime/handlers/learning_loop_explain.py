from __future__ import annotations

from runtime.learning_loop import PolicyUpdateProposal, explain_policy_update

CANON_THIN_HANDLER = True

def handle_learning_loop_explain(proposal: PolicyUpdateProposal) -> str:
    return explain_policy_update(proposal)
