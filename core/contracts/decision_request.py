from __future__ import annotations

"""Compat shim: core.contracts.* forwards to kernel.*."""

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_request

from kernel.decision_request import DecisionRequest

__all__ = ['DecisionRequest']
