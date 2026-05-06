from __future__ import annotations

from observability.platform.telemetry.contracts import AppendOnlyTelemetryStore as EventStore


class TelemetryEmitter:
    def __init__(self, *, store: EventStore):
        self._store = store

    def emit(self, *, tenant_id: str, user_id: str, event_type: str, payload: dict) -> None:
        self._store.append(tenant_id=tenant_id, user_id=user_id, event_type=event_type, payload=payload)
