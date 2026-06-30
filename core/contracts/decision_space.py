"""Compat shim: core.contracts.* forwards to kernel.*."""

from __future__ import annotations



from kernel.decision_space import DecisionSpace

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_space


__all__ = ['DecisionSpace']
