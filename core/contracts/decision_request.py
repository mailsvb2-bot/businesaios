"""Compat shim: core.contracts.* forwards to kernel.*."""

from __future__ import annotations

from kernel.decision_request import DecisionRequest

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_request


__all__ = ['DecisionRequest']
