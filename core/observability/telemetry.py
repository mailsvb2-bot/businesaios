from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class TelemetryEvent:
    name: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    tenant_id: str = ""
    correlation_id: str = ""


def emit_telemetry(event: TelemetryEvent | str, payload: Mapping[str, Any] | None = None, **metadata: Any) -> dict[str, Any]:
    if isinstance(event, TelemetryEvent):
        return {
            "name": event.name,
            "payload": dict(event.payload or {}),
            "tenant_id": event.tenant_id,
            "correlation_id": event.correlation_id,
        }
    return {"name": str(event), "payload": dict(payload or {}), **metadata}


__all__ = ["TelemetryEvent", "emit_telemetry"]


# Runtime telemetry owns spans. Core keeps a compatibility import only so older
# surfaces do not fork span semantics or correlation propagation.
from runtime.observability.telemetry import telegram_api_span

__all__ = ["TelemetryEvent", "emit_telemetry", "telegram_api_span"]
