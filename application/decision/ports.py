"""Canonical protocols for the decision application surface.

Recommendation services have no execution authority. The only execution port
accepted here is compatible with ``RuntimeExecutor.execute(envelope)``;
decision issuance and execution remain separate capabilities.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DecisionExecutionPortProtocol(Protocol):
    def execute(self, envelope: object) -> Any: ...


@runtime_checkable
class ObservabilityPortProtocol(Protocol):
    def audit_events(self) -> tuple[str, ...]: ...


CANON_CORE_DECISION_APPLICATION_PORTS = True
CANON_DECISION_EXECUTION_PORT_ENVELOPE_ONLY = True

__all__ = [
    "CANON_CORE_DECISION_APPLICATION_PORTS",
    "CANON_DECISION_EXECUTION_PORT_ENVELOPE_ONLY",
    "DecisionExecutionPortProtocol",
    "ObservabilityPortProtocol",
]
