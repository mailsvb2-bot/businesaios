"""Safety gate wrapper for DecisionCore."""

from __future__ import annotations

import logging
from typing import Any

_LOG = logging.getLogger(__name__)


def gate_action_or_raise(*, action: str, payload: dict[str, Any], tenant_id: str, user_id: str, event_log: Any, trace: Any) -> tuple[bool, str, dict[str, Any]]:
    from application.decision_policy.safety import gate_decision_action

    gate_ok, gate_reason, gate_debug = gate_decision_action(
        action=action,
        payload=dict(payload) if isinstance(payload, dict) else {},
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        event_log=event_log,
    )
    if trace is not None and hasattr(trace, "try_add_step"):
        trace.try_add_step(name="action_safety_gate", input={"action": action}, output={"ok": gate_ok, "reason": gate_reason, **gate_debug})
    if not gate_ok:
        debug = gate_debug if isinstance(gate_debug, dict) else {}
        _LOG.warning(
            "decision blocked action=%s reason=%s control=%s payload_keys=%s details=%s",
            action, gate_reason, debug.get("control"),
            sorted(str(key) for key in payload),
            dict(debug.get("details") or {}) if isinstance(debug.get("details"), dict) else {},
        )
        event_log.emit(
            event_type="decision_blocked",
            source="decision_core",
            user_id=str(user_id),
            decision_id="",
            correlation_id="",
            payload={"action": str(action), "reason": str(gate_reason), "debug": gate_debug},
        )
        raise RuntimeError(f"DECISION_BLOCKED:{gate_reason}")
    return gate_ok, gate_reason, gate_debug
