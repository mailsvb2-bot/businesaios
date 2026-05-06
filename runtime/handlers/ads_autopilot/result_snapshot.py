from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AutopilotResultSnapshot:
    status: str
    stop_loss_allowed: Any
    stop_loss_reason: Any
    commands_count: int
    apply_status: str


def snapshot_autopilot_result(res: Any) -> AutopilotResultSnapshot:
    status = str(getattr(res, "status", "unknown") or "unknown")
    stop_loss = getattr(res, "stop_loss", {}) or {}
    commands = ((getattr(res, "plan", {}) or {}).get("commands") or [])
    applied = getattr(res, "applied", {}) or {}
    return AutopilotResultSnapshot(
        status=status,
        stop_loss_allowed=stop_loss.get("allowed"),
        stop_loss_reason=stop_loss.get("reason"),
        commands_count=len(commands),
        apply_status=str(applied.get("status", "unknown") or "unknown"),
    )
