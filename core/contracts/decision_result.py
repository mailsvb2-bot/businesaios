from __future__ import annotations

"""Compat shim: core.contracts.* forwards to kernel.*."""

CANON_KERNEL_DECISION_CONTRACT_COMPAT = True
# canonical owner: kernel.decision_result

from kernel.decision_result import *  # noqa: F401,F403

__all__ = ['DecisionResult']
