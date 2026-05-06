from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class BehaviorTelemetryV1:
    user_id: str
    tenant_id: str
    ts_ms: int
    kind: str

    # Stable identifiers for UX
    button_id: Optional[str] = None
    screen: Optional[str] = None

    # Timing / interaction
    latency_ms: Optional[int] = None
    delta_ms: Optional[int] = None

    # Audio (optional; populated by WebApp later)
    audio_id: Optional[str] = None
    audio_pos_ms: Optional[int] = None
    audio_total_ms: Optional[int] = None
    audio_completed: Optional[bool] = None

    # Extra dims (safe)
    dims: Optional[Dict[str, Any]] = None

    def to_event_payload(self) -> Dict[str, Any]:
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
