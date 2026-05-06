from __future__ import annotations

from typing import Any


def render_autopilot_result_text(snapshot: Any) -> str:
    return "\n".join(
        [
            "🤖 Ads Autopilot",
            f"status: {getattr(snapshot, 'status', 'unknown')}",
            f"stop_loss: {getattr(snapshot, 'stop_loss_allowed', None)} ({getattr(snapshot, 'stop_loss_reason', None)})",
            f"commands: {getattr(snapshot, 'commands_count', 0)}",
            f"apply: {getattr(snapshot, 'apply_status', 'unknown')}",
        ]
    )


def render_gate_error_text(exc: Exception) -> str:
    reason = exc.__class__.__name__ if exc is not None else "GateViolation"
    return f"⏳ Ads Autopilot: cooldown/gate ({reason})"
