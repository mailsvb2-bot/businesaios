from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BehaviorTelemetryV1:
    user_id: str
    tenant_id: str
    ts_ms: int
    kind: str

    # Stable identifiers for UX
    button_id: str | None = None
    screen: str | None = None

    # Timing / interaction
    latency_ms: int | None = None
    delta_ms: int | None = None

    # Audio (optional; populated by WebApp later)
    audio_id: str | None = None
    audio_pos_ms: int | None = None
    audio_total_ms: int | None = None
    audio_completed: bool | None = None

    # Extra dims (safe)
    dims: dict[str, Any] | None = None

    def to_event_payload(self) -> dict[str, Any]:
        return {
            "schema": "behavior_telemetry@v1",
            "kind": self.kind,
            "button_id": self.button_id,
            "screen": self.screen,
            "latency_ms": self.latency_ms,
            "delta_ms": self.delta_ms,
            "audio_id": self.audio_id,
            "audio_pos_ms": self.audio_pos_ms,
            "audio_total_ms": self.audio_total_ms,
            "audio_completed": self.audio_completed,
            "dims": self.dims or {},
        }
