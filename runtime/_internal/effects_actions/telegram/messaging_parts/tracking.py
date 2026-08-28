from __future__ import annotations

from typing import Any


def emit_warning(
    event_log: Any,
    *,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    reason: str,
    error: Exception | None = None,
) -> None:
    try:
        if event_log is None or not hasattr(event_log, "emit"):
            return
        event_log.emit(
            event_type="messaging_effect_warning",
            source="runtime_effects.messaging",
            user_id=str(user_id or "unknown"),
            decision_id=str(decision_id or "-"),
            correlation_id=str(correlation_id or "-"),
            payload={
                "reason": str(reason),
                "error": error.__class__.__name__ if error is not None else None,
            },
        )
    except Exception:
        return


def track_delivery(
    self: Any,
    *,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    channel: str,
    text: str,
    ok: bool,
    meta: dict,
) -> None:
    if self.event_log is None or not hasattr(self.event_log, "emit"):
        return
    self.event_log.emit(
        event_type="message_sent",
        source="runtime_effects",
        user_id=str(user_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload={
            "channel": str(channel),
            "text": str(text),
            "ok": bool(ok),
            "meta": dict(meta or {}),
        },
    )


def _emit_business_event(
    event_log: Any,
    *,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    event_log.emit(
        event_type=str(event_type),
        source="runtime_effects.track",
        user_id=str(user_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload=dict(payload),
    )


def track_business_event(
    self: Any,
    *,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    track_event_type: str | None,
    track_payload: dict | None,
) -> None:
    if (
        not isinstance(track_event_type, str)
        or not track_event_type.strip()
        or self.event_log is None
    ):
        return
    try:
        payload = {key: value for key, value in (track_payload.items() if isinstance(track_payload, dict) else ()) if not str(key).startswith('_provider_')}
        _emit_business_event(
            self.event_log,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            event_type=track_event_type.strip(),
            payload=payload,
        )
        additional = payload.get("additional_track_events")
        if isinstance(additional, list):
            for event in additional:
                if not isinstance(event, dict):
                    continue
                event_type = str(event.get("event_type") or "").strip()
                if not event_type:
                    continue
                event_payload = event.get("payload")
                _emit_business_event(
                    self.event_log,
                    user_id=user_id,
                    decision_id=decision_id,
                    correlation_id=correlation_id,
                    event_type=event_type,
                    payload=event_payload if isinstance(event_payload, dict) else {},
                )
    except Exception as exc:
        emit_warning(
            self.event_log,
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            reason="track_event_emit_failed",
            error=exc,
        )
