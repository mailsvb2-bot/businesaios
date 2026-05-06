from __future__ import annotations

from application.decision.ports import (
    CANON_CORE_DECISION_APPLICATION_PORTS,
    DecisionExecutionPortProtocol,
    ObservabilityPortProtocol,
)

CANON_CORE_APPLICATION_PORTS_COMPAT = True

__all__ = [
    "CANON_CORE_APPLICATION_PORTS_COMPAT",
    "CANON_CORE_DECISION_APPLICATION_PORTS",
    "DecisionExecutionPortProtocol",
    "ObservabilityPortProtocol",
]
