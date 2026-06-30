"""Compat shim: core.contracts.* forwards to kernel.*."""

from __future__ import annotations



from kernel.decision_candidate import DecisionCandidate

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_candidate


__all__ = ['DecisionCandidate']
