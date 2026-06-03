from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from collections.abc import Mapping


def build_behavior_structured_event(kind: str, payload: Mapping[str, Any]) -> dict[str, object]:
    return {
        "event_type": "behavior_structured",
        "kind": kind,
        "payload": dict(payload),
        "timestamp": datetime.now(UTC),
    }
