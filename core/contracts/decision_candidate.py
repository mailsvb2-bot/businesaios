from __future__ import annotations

"""Compat shim: core.contracts.* forwards to kernel.*."""

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_candidate

from kernel.decision_candidate import DecisionCandidate

__all__ = ['DecisionCandidate']
