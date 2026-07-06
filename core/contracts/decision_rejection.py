"""Compat shim: core.contracts.* forwards to kernel.*."""

from __future__ import annotations

from kernel.decision_rejection import DecisionRejection

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_rejection


__all__ = ['DecisionRejection']
