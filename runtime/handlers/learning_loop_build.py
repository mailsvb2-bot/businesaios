from __future__ import annotations

CANON_THIN_HANDLER = True
from runtime.learning_loop import LearningBatch, PolicyUpdateProposal, build_policy_update_proposal


def handle_learning_loop_build(batch: LearningBatch) -> PolicyUpdateProposal:
    return build_policy_update_proposal(batch)
