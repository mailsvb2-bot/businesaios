"""Compat shim: core.contracts.* forwards to kernel.*."""

from __future__ import annotations

from kernel.decision_reason import DecisionReason

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_reason


__all__ = ['DecisionReason']
