from __future__ import annotations

"""Compat shim: core.contracts.* forwards to kernel.*."""

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_space

from kernel.decision_space import DecisionSpace

__all__ = ['DecisionSpace']
