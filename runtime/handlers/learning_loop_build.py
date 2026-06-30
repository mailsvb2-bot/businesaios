from __future__ import annotations

from runtime.learning_loop import LearningBatch, PolicyUpdateProposal, build_policy_update_proposal

CANON_THIN_HANDLER = True

def handle_learning_loop_build(batch: LearningBatch) -> PolicyUpdateProposal:
    return build_policy_update_proposal(batch)
