from __future__ import annotations

"""Safety gate wrapper for DecisionCore."""

from typing import Any, Dict, Tuple


def gate_action_or_raise(*, action: str, payload: Dict[str, Any], tenant_id: str, user_id: str, event_log: Any, trace: Any) -> Tuple[bool, str, Dict[str, Any]]:
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
