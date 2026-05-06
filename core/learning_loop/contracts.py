"""Learning-loop contracts. Execution contract: DecisionCore -> RuntimeExecutor (single path)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyUpdateProposal:
    """Proposal produced by learning loop from a batch (advisory only)."""
    policy_name: str
    reason: str
    confidence: float = 0.0


__all__ = ["PolicyUpdateProposal"]
