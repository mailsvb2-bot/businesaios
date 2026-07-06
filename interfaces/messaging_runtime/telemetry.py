from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from time import time
from typing import Any


def _now_ms() -> int:
    return int(time() * 1000)


@dataclass(frozen=True)
class RuntimeTelemetryRecord:
    event_name: str
    correlation_id: str
    channel: str
    severity: str
    component: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    timestamp_ms: int = field(default_factory=_now_ms)

    def validate(self) -> None:
        if not self.event_name:
            raise ValueError("event_name is required")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")
        if not self.channel:
            raise ValueError("channel is required")
        if not self.severity:
            raise ValueError("severity is required")
        if not self.component:
            raise ValueError("component is required")
        if int(self.timestamp_ms) <= 0:
            raise ValueError("timestamp_ms must be > 0")


class InMemoryTelemetrySink:
    def __init__(self) -> None:
        self._records: list[RuntimeTelemetryRecord] = []

    def emit(self, record: RuntimeTelemetryRecord) -> None:
        record.validate()
        self._records.append(record)

    def snapshot(self) -> list[dict]:
        return [asdict(item) for item in self._records]


class AuditTrailStore:
    def __init__(self) -> None:
        self._records: list[RuntimeTelemetryRecord] = []

    def append(self, record: RuntimeTelemetryRecord) -> None:
        record.validate()
        self._records.append(record)

    def snapshot(self):
        return list(self._records)


class RuntimeAnomalyHooks:
    def __init__(self) -> None:
        self._anomalies: list[dict] = []

    def inspect(self, record: RuntimeTelemetryRecord) -> None:
        payload_text = str(record.payload).lower()
        base = {
            "correlation_id": record.correlation_id,
            "channel": record.channel,
            "timestamp_ms": int(record.timestamp_ms),
        }
        if record.severity.lower() in {"error", "critical"}:
            self._anomalies.append({"kind": "runtime_error_event", **base})
        elif "backpressure" in payload_text:
            self._anomalies.append({"kind": "backpressure_signal", **base})
        elif "dead_letter" in payload_text:
            self._anomalies.append({"kind": "dead_letter_signal", **base})
        elif "transport_not_configured" in payload_text:
            self._anomalies.append({"kind": "transport_not_configured", **base})

    def snapshot(self):
        return list(self._anomalies)


class RuntimeTelemetryFacade:
    def __init__(self, *, sink: InMemoryTelemetrySink, audit_trail: AuditTrailStore, anomaly_hooks: RuntimeAnomalyHooks) -> None:
        self._sink = sink
        self._audit_trail = audit_trail
        self._anomaly_hooks = anomaly_hooks

    def emit(self, *, event_name: str, correlation_id: str, channel: str, severity: str, component: str, payload: dict | None = None) -> None:
        record = RuntimeTelemetryRecord(
            event_name=event_name,
            correlation_id=correlation_id,
            channel=channel,
            severity=severity,
            component=component,
            payload=dict(payload or {}),
        )
        record.validate()
        self._audit_trail.append(record)
        self._anomaly_hooks.inspect(record)
        self._sink.emit(record)
