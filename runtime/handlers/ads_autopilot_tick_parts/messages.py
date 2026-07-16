from __future__ import annotations

from typing import Any

from runtime.handlers.delivery_contract import delivery_kwargs


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
    tenant_id = str(payload.get("tenant_id") or "").strip()
    user_id = str(payload.get("user_id") or "").strip()
    if not tenant_id:
        raise RuntimeError("TENANT_ID_REQUIRED")
    if not user_id:
        raise RuntimeError("USER_ID_REQUIRED")
    event_payload = dict(track_payload or {})
    event_payload.setdefault("tenant_id", tenant_id)
    return effects.send_message(
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        tenant_id=tenant_id,
        user_id=user_id,
        text=str(text),
        track_event_type=str(track_event_type),
        track_payload=event_payload,
        **delivery_kwargs(payload),
    )
