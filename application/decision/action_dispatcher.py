from __future__ import annotations

from dataclasses import dataclass

from application.decision.ports import DecisionExecutionPortProtocol


@dataclass(frozen=True)
class ActionDispatcher:
    """Canonical core-owned dispatcher for the single decision-execution path."""

    decision_execution_port: DecisionExecutionPortProtocol

    def dispatch(self, action: object) -> dict:
        return self.decision_execution_port.decide_and_execute(action)


__all__ = ["ActionDispatcher"]
