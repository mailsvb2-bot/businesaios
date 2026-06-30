"""Compat shim: core.contracts.* forwards to kernel.*."""

from __future__ import annotations



from kernel.decision_trace import DecisionTrace

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_trace


__all__ = ['DecisionTrace']
