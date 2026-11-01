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
    """Only the canonical single-message action, never arbitrary zero-cost actions.

    A priced send is still charged against the original financial/action budget.
    """
    if str(action) != "send_message@v1":
        return False
    try:
        cost = float(payload.get("estimated_cost", 0.0) or 0.0)
    except (ValueError, TypeError, OverflowError):
        return False
    return cost == 0.0
