from __future__ import annotations

"""Compat shim: core.contracts.* forwards to kernel.*."""

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_context

from kernel.decision_context import *  # noqa: F401,F403

__all__ = ['DecisionContext']
