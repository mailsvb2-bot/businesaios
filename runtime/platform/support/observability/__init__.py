from __future__ import annotations

from uuid import uuid4

from observability.logger import get_logger, log_kv
from runtime.lazy_namespace import install_module_aliases

CANON_RUNTIME_SUPPORT_OBSERVABILITY_NAMESPACE = True
CANON_COMPAT_SHIM = True
CANON_RUNTIME_SUPPORT_OBSERVABILITY_LOGGING = True

class Alerts:
    def fire(self, name: str, payload: dict) -> dict:
        return {"alert": name, "payload": dict(payload)}

class Dashboards:
    def render(self, metrics: dict) -> dict:
        return dict(metrics)

class ErrorReporting:
    def report(self, exc: Exception) -> dict[str, str]:
        return {"error_type": type(exc).__name__, "message": str(exc)}

class HealthChecks:
    def healthy(self, checks: dict[str, bool]) -> bool:
        return all(checks.values())

class Heartbeat:
    def beat(self) -> dict[str, str]:
        return {"heartbeat": "ok"}

class RateLimitedLogging:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def allow(self, key: str, limit: int) -> bool:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key] <= limit

class StructuredEvents:
    def build(self, name: str, **kwargs) -> dict:
        payload = {"event": name}
        payload.update(kwargs)
        return payload

class Telemetry:
    def __init__(self) -> None:
        self._items: list[dict] = []

    def emit(self, name: str, payload: dict) -> None:
        self._items.append({"name": name, "payload": dict(payload)})

    def items(self) -> list[dict]:
        return list(self._items)

class TraceRecorder:
    def __init__(self) -> None:
        self._events: list[dict] = []

    def record(self, name: str, payload: dict) -> None:
        self._events.append({"name": name, "payload": dict(payload)})

    def events(self) -> list[dict]:
        return list(self._events)

def new_correlation_id() -> str:
    return uuid4().hex

install_module_aliases(__name__, {"metrics": "runtime.observability.metrics"})

__all__ = [
    "Alerts",
    "CANON_COMPAT_SHIM",
    "CANON_RUNTIME_SUPPORT_OBSERVABILITY_LOGGING",
    "CANON_RUNTIME_SUPPORT_OBSERVABILITY_NAMESPACE",
    "Dashboards",
    "ErrorReporting",
    "HealthChecks",
    "Heartbeat",
    "RateLimitedLogging",
    "StructuredEvents",
    "Telemetry",
    "TraceRecorder",
    "get_logger",
    "log_kv",
    "new_correlation_id",
]
