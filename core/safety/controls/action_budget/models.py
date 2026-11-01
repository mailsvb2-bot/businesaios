from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from contracts.messaging_channels import ALL_CHANNELS


@dataclass(frozen=True)
class ActionBudget:
    max_cost: float
    max_actions: int


def is_routine_reply(action: str, payload: Mapping[str, Any]) -> bool:
    """Verified single-recipient inbound replies do not spend autonomous budgets."""
    if str(action) != "send_message@v1":
        return False
    marker = payload.get("meta")
    marker = marker.get("inbound_user_reply") if isinstance(marker, Mapping) else None
    if not isinstance(marker, Mapping) or marker.get("channel") not in ALL_CHANNELS:
        return False
    update_id = marker.get("update_id")
    if type(update_id) is not int or update_id < 0 or not str(payload.get("user_id") or "").strip():
        return False
    try:
        cost = float(payload.get("estimated_cost", 0.0) or 0.0)
    except (ValueError, TypeError, OverflowError):
        return False
    return cost == 0.0
