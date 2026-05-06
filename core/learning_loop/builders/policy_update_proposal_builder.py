from __future__ import annotations

from ..contracts import PolicyUpdateProposal
from ..types import LearningBatch


def build_low_confidence_proposal(batch: LearningBatch) -> PolicyUpdateProposal:
    return PolicyUpdateProposal(
        policy_name="unknown",
        reason=f"learning_batch:{batch.batch_id}",
        confidence=0.0,
    )
