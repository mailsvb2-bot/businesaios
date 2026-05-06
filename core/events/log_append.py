from __future__ import annotations

from typing import Any


def normalize_legacy_event(event: dict[str, Any]) -> tuple[str, str, str, dict[str, Any], int | None]:
    if not isinstance(event, dict):
        raise ValueError("event must be dict")

    event_type = event.get("event_type") or event.get("type")
    source = event.get("source", "unknown")
    user_id = event.get("user_id")
    if user_id is None:
        user_id = "system"

    payload = dict(event.get("payload") or {})
    for key, value in event.items():
        if key in {
            "event_id",
            "user_id",
            "source",
            "event_type",
            "type",
            "timestamp_ms",
            "timestamp",
            "payload",
            "decision_id",
            "correlation_id",
        }:
            continue
        payload.setdefault(key, value)

    timestamp_ms = event.get("timestamp_ms")
    if timestamp_ms is None and "timestamp" in event:
        try:
            timestamp_ms = int(event["timestamp"])
        except Exception:
            timestamp_ms = None

    return str(event_type), str(source), str(user_id), payload, timestamp_ms
