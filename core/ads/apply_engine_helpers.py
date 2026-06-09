"""Helpers for AdsApplyEngine: rollback, protocol."""

from __future__ import annotations

from typing import Any, Protocol


class AdsApplyPort(Protocol):
    def perform_apply(self, tenant_id: str, plan: Any) -> dict[str, Any]: ...


def best_effort_rollback(
    apply_port: AdsApplyPort, *, tenant_id: str, plan: Any
) -> dict[str, Any] | None:
    """Try to apply undo commands if present.

    Convention:
      AdsCommand.payload may contain {"undo": {...}} as an inverse op spec.
    """
    cmds = getattr(plan, "commands", None)
    if not isinstance(cmds, list):
        return None
    undo_cmds = []
    for c in reversed(cmds):
        payload = getattr(c, "payload", {}) or {}
        undo = payload.get("undo")
        if isinstance(undo, dict):
            undo_cmds.append(
                type(c)(
                    platform=str(getattr(c, "platform", "")),
                    action=str(undo.get("action") or getattr(c, "action", "")),
                    payload=dict(undo.get("payload") or {}),
                )
            )
    if not undo_cmds:
        return {"status": "skipped", "reason": "no_undo_hints"}
    try:
        tmp_plan = type(plan)(commands=undo_cmds, notes="rollback")
        out = apply_port.perform_apply(tenant_id, tmp_plan)
        return {"status": "attempted", "provider": out}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
