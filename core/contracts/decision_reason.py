from __future__ import annotations

"""Compat shim: core.contracts.* forwards to kernel.*."""

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_reason

from kernel.decision_reason import DecisionReason

__all__ = ['DecisionReason']
