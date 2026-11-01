from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionBudget:
    max_cost: float
    max_actions: int

from datetime import datetime, timezone
from typing import Any, Mapping


def routine_reply_day() -> str:
    """UTC calendar-day bucket for ordinary non-billable single-message replies."""
    return datetime.now(timezone.utc).date().isoformat()


def is_routine_reply(action: str, payload: Mapping[str, Any]) -> bool:
    """Only a signed DecisionCore reply tied to a canonical Telegram update.

    Other messages, even non-billable marketing sends, retain normal budgets.
    """
    if str(action) != "send_message@v1":
        return False
    marker = payload.get("meta")
    marker = marker.get("inbound_user_reply") if isinstance(marker, Mapping) else None
    if not isinstance(marker, Mapping) or marker.get("channel") != "telegram":
        return False
    update_id = marker.get("update_id")
    if type(update_id) is not int or update_id < 0 or not str(payload.get("user_id") or "").strip():
        return False
    try:
        cost = float(payload.get("estimated_cost", 0.0) or 0.0)
    except (ValueError, TypeError, OverflowError):
        return False
    return cost == 0.0
