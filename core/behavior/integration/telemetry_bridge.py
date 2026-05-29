from __future__ import annotations

from datetime import UTC, datetime, timedelta


class PolicyDeniedTelemetryEmitter:
    def __init__(self) -> None:
        self._last_emitted_at: dict[str, datetime] = {}

    def maybe_emit(self, entity_id: str, policy_denials: dict[str, int], now: datetime | None = None) -> dict[str, object] | None:
        if not policy_denials:
            return None
        current_time = now or datetime.now(UTC)
        last_time = self._last_emitted_at.get(entity_id)
        if last_time and current_time - last_time < timedelta(seconds=60):
            return None
        self._last_emitted_at[entity_id] = current_time
        return {
            "event_type": "behavior_telemetry",
            "kind": "policy_denied",
            "entity_id": entity_id,
            "payload": {
                "policy_denials": dict(policy_denials),
            },
            "timestamp": current_time,
        }
