"""Compat shim: core.contracts.* forwards to kernel.*."""

from __future__ import annotations

from kernel.decision_result import DecisionResult

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_result


__all__ = ['DecisionResult']
