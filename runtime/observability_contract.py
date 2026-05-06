from __future__ import annotations
from typing import Protocol, Any

RUNTIME_OBSERVABILITY_CONTRACT_VERSION = "ROC-CONTRACT-V1"

class RuntimeAuditPort(Protocol):
    def emit_audit(self, event: str, payload: dict[str, Any]) -> None: ...

class RuntimeMetricsPort(Protocol):
    def emit_metric(self, name: str, value: float) -> None: ...
