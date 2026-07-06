"""Compat shim: core.contracts.* forwards to kernel.*."""

from __future__ import annotations

from kernel.decision_context import DecisionContext

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_context


__all__ = ['DecisionContext']
