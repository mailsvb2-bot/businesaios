from __future__ import annotations

from collections.abc import Mapping

_SUCCESS_STATUSES = frozenset(
    {
        "captured",
        "completed",
        "confirmed",
        "paid",
        "succeeded",
        "success",
    }
)
_FAILURE_STATUSES = frozenset(
    {
        "canceled",
        "cancelled",
        "declined",
        "failed",
        "failure",
        "refunded",
    }
)
_SEMANTIC_SUCCESS_EVENT_TYPES = frozenset(
    {
        "booking_confirmed@v1",
        "payment_captured",
        "payment_succeeded",
        "purchase_success",
    }
)


def resolve_outcome_success(
    event_type: str,
    payload: Mapping[str, object],
) -> bool | None:
    """Resolve real business success without blessing arbitrary event types."""

    for key in ("success", "ok"):
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    status = str(payload.get("status") or "").strip().lower()
    if status in _SUCCESS_STATUSES:
        return True
    if status in _FAILURE_STATUSES:
        return False
    if str(event_type) in _SEMANTIC_SUCCESS_EVENT_TYPES:
        return True
    return None


__all__ = ["resolve_outcome_success"]
