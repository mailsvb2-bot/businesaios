from __future__ import annotations

from dataclasses import replace
from typing import Callable

from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging_policy.policy_plan import PolicyPlan


def execute_policy_plan(
    *,
    plan: PolicyPlan,
    base_message: OutboundMessage,
    send_once: Callable[[OutboundMessage], tuple[bool, dict]],
) -> tuple[bool, dict]:
    attempts: list[dict] = []
    last_meta: dict = {}

    if not plan.ordered_channels:
        return False, {
            "policy": {
                "ordered_channels": [],
                "reason_codes": list(plan.reason_codes),
                "terminal_reason": plan.terminal_reason,
                "attempts": [],
            }
        }

    for channel in plan.ordered_channels:
        msg = replace(base_message, channel=channel)
        ok, meta = send_once(msg)
        meta = dict(meta or {})
        attempts.append(
            {
                "channel": channel,
                "ok": bool(ok),
                "meta": meta,
            }
        )
        last_meta = meta
        if ok:
            out = dict(meta)
            out["policy"] = {
                "ordered_channels": list(plan.ordered_channels),
                "reason_codes": list(plan.reason_codes),
                "terminal_reason": plan.terminal_reason,
                "attempts": attempts,
                "selected_channel": channel,
            }
            return True, out

    out = dict(last_meta or {})
    out["policy"] = {
        "ordered_channels": list(plan.ordered_channels),
        "reason_codes": list(plan.reason_codes),
        "terminal_reason": "all_attempts_failed",
        "attempts": attempts,
    }
    return False, out
