from __future__ import annotations

from datetime import datetime

from core.behavior.integration.telemetry_bridge import PolicyDeniedTelemetryEmitter
from core.behavior.integration.telemetry_metrics_bridge import behavior_metrics_from_payload


class ThinBehaviorTelemetryAdapter:
    def __init__(self) -> None:
        self._denial_emitter = PolicyDeniedTelemetryEmitter()

    def build_events(self, entity_id: str, payload: dict[str, object], now: datetime | None = None) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        behavior = dict(payload.get("behavior", {}))
        denial_event = self._denial_emitter.maybe_emit(entity_id, dict(behavior.get("policy_denials", {})), now=now)
        if denial_event is not None:
            events.append(denial_event)
        events.append(
            {
                "event_type": "behavior_metrics",
                "entity_id": entity_id,
                "payload": behavior_metrics_from_payload(payload),
                "timestamp": now or datetime.utcnow(),
            }
        )
        return events
