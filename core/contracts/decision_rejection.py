from __future__ import annotations

"""Compat shim: core.contracts.* forwards to kernel.*."""

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_rejection

from kernel.decision_rejection import DecisionRejection

__all__ = ['DecisionRejection']
