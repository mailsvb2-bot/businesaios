from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

RUNTIME_DECISION_CORE_CONTRACT_VERSION = "1.0"
CANON_RUNTIME_DECISION_CORE_CONTRACT = True


@runtime_checkable
class RuntimeDecisionCorePort(Protocol):
    decide: Any

    def issue(self, request: object) -> object: ...


__all__ = [
    "RUNTIME_DECISION_CORE_CONTRACT_VERSION",
    "CANON_RUNTIME_DECISION_CORE_CONTRACT",
    "RuntimeDecisionCorePort",
]
