"""Compatibility dispatcher surface for historical ``core.decision`` imports.

Canonical owner stays in ``application.decision.action_dispatcher``.
This shim preserves the visible path without introducing a second dispatcher
brain or bypassing the single decision-execution contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from application.decision.ports import DecisionExecutionPortProtocol

CANON_COMPAT_SHIM = True
CANON_CORE_DECISION_ACTION_DISPATCHER_COMPAT = True
CANONICAL_OWNER_MODULE = "application.decision.action_dispatcher"

@dataclass(frozen=True)
class ActionDispatcher:
    decision_execution_port: DecisionExecutionPortProtocol

    def dispatch(self, action: object) -> dict:
        return self.decision_execution_port.decide_and_execute(action)


__all__ = [
    "ActionDispatcher",
    "CANON_COMPAT_SHIM",
    "CANON_CORE_DECISION_ACTION_DISPATCHER_COMPAT",
    "CANONICAL_OWNER_MODULE",
]
