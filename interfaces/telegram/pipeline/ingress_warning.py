from __future__ import annotations

from typing import Any


def emit_ingress_warning(event_log: Any, *, user_id: str, reason: str, error: Exception | None = None) -> None:
    if event_log is None or not hasattr(event_log, "emit"):
        return
    try:
        event_log.emit(
            event_type="telegram_ingress_warning",
            source="telegram_ingress",
            user_id=str(user_id or "unknown"),
            decision_id="-",
            correlation_id="-",
            payload={
                "reason": str(reason),
                "error": error.__class__.__name__ if error is not None else None,
            },
        )
    except Exception:
        return
