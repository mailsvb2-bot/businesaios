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
    """Only zero-cost, single-recipient, inbound-bound sends bypass autonomous budgets."""
    if action != "send_message@v1":
        return False
    meta = payload.get("meta")
    proof = meta.get("inbound_user_reply") if isinstance(meta, Mapping) else None
    if not isinstance(proof, Mapping) or proof.get("channel") not in ALL_CHANNELS:
        return False
    channel, event_id = proof["channel"], proof.get("update_id")
    if channel == "telegram":
        valid = type(event_id) is int and event_id >= 0
    else:
        valid = (isinstance(event_id, str) and 0 < len(event_id.strip()) <= 256
                 and bool(proof.get("tenant_id"))
                 and str(proof["tenant_id"]) == str(payload.get("tenant_id") or ""))
    if not valid or not str(payload.get("user_id") or "").strip():
        return False
    if payload.get("recipient_count") not in (None, 1):
        return False
    try:
        return float(payload.get("estimated_cost") or 0.0) == 0.0
    except (ValueError, TypeError, OverflowError):
        return False
