from __future__ import annotations

from typing import Any


def send_autopilot_message(
    *,
    effects,
    payload: dict[str, Any],
    decision_id: str,
    correlation_id: str,
    text: str,
    track_event_type: str,
    track_payload: dict | None = None,
):
    return effects.send_message(
        decision_id=str(decision_id or payload.get("decision_id") or ""),
        correlation_id=str(correlation_id or payload.get("correlation_id") or ""),
        user_id=str(payload.get("user_id") or ""),
        chat_id=str(payload.get("chat_id") or ""),
        text=str(text),
        track_event_type=str(track_event_type),
        track_payload=dict(track_payload or {}),
    )
