from __future__ import annotations

from dataclasses import asdict
from typing import Protocol

from .contracts import PolicyUpdateProposal
from .types import LearningBatch


class LearningLoopService(Protocol):
    def run(self, *, policy_id: str, subject_id: str) -> dict[str, object]: ...


class DefaultLearningLoopService:
    """Thin canonical adapter. Produces advisory output only."""

    def run(self, *, policy_id: str, subject_id: str) -> dict[str, object]:
        proposal = build_policy_update_proposal(LearningBatch(batch_id=f"{policy_id}:{subject_id}"))
        return {
            "status": "proposed",
            "policy_id": str(policy_id),
            "subject_id": str(subject_id),
            "proposal": asdict(proposal),
        }


def build_policy_update_proposal(batch: LearningBatch) -> PolicyUpdateProposal:
    return PolicyUpdateProposal(
        policy_name="unknown",
        reason=f"batch:{batch.batch_id}",
        confidence=0.0,
    )


__all__ = [
    "DefaultLearningLoopService",
    "LearningLoopService",
    "build_policy_update_proposal",
]
