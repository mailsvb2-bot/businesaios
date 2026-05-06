from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def build_behavior_structured_event(kind: str, payload: Mapping[str, Any]) -> dict[str, object]:
    return {
        "event_type": "behavior_structured",
        "kind": kind,
        "payload": dict(payload),
        "timestamp": datetime.now(timezone.utc),
    }
