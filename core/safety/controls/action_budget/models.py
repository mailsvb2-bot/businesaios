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
    tenant_matches = bool(proof.get("tenant_id")) and str(proof["tenant_id"]) == str(payload.get("tenant_id") or "")
    valid = (type(event_id) is int and event_id >= 0) if channel == "telegram" else (
        isinstance(event_id, str) and bool(event_id.strip()) and len(event_id) <= 256)
    recipient, count = payload.get("user_id"), payload.get("recipient_count")
    if (not tenant_matches or not valid or not isinstance(recipient, str) or not recipient.strip()
            or proof.get("user_id") != recipient
            or (payload.get("channel") is not None and str(payload["channel"]).strip().lower() != channel)
            or (proof.get("chat_id") and str(payload.get("chat_id") or "") != str(proof["chat_id"]))
            or (count is not None and (type(count) is not int or count != 1))):
        return False
    try:
        return float(payload.get("estimated_cost") or 0.0) == 0.0
    except (ValueError, TypeError, OverflowError):
        return False
