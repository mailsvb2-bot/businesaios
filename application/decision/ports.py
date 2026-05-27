from __future__ import annotations

"""Canonical core-owned protocol names for the decision application surface.

The runtime package keeps a physical compatibility file for regression gates,
while the actual import identity stays anchored here to avoid split-brain API
ownership between core and runtime.
"""

from typing import Protocol

DecisionExecutionPortProtocol = type("DecisionExecutionPortProtocol", (Protocol,), {})
ObservabilityPortProtocol = type("ObservabilityPortProtocol", (Protocol,), {})

CANON_CORE_DECISION_APPLICATION_PORTS = True

__all__ = [
    "CANON_CORE_DECISION_APPLICATION_PORTS",
    "DecisionExecutionPortProtocol",
    "ObservabilityPortProtocol",
]
