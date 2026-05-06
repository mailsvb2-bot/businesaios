from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from contracts.action_result import ActionResult


CANON_EFFECTOR_RESULT = True


@dataclass(frozen=True)
class EffectorResult:
    attempted: bool
    executed: bool
    verified: bool
    status: str
    external_system: str
    external_ref: str | None
    code: str
    message: str
    operator_required: bool
    retry_kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    def action_status(self) -> str:
        if self.executed:
            return "accepted"
        if self.operator_required:
            return "operator_required"
        if self.retry_kind in {"recoverable", "temporary"}:
            return "temporary_failure"
        return "failed"

    def as_dict(self) -> dict[str, Any]:
        return {
            "attempted": bool(self.attempted),
            "executed": bool(self.executed),
            "verified": bool(self.verified),
            "status": str(self.status),
            "external_system": str(self.external_system),
            "external_ref": self.external_ref,
            "code": str(self.code),
            "message": str(self.message),
            "operator_required": bool(self.operator_required),
            "retry_kind": str(self.retry_kind),
            "payload": dict(self.payload or {}),
            "evidence": dict(self.evidence or {}),
        }

    def to_action_result(self, *, action_id: str, action_type: str) -> ActionResult:
        return ActionResult(
            action_id=str(action_id),
            status=self.action_status(),
            message=str(self.message),
            payload={
                "action_type": str(action_type),
                "effector": self.as_dict(),
                "external_system": str(self.external_system),
                "external_ref": self.external_ref,
                "evidence": dict(self.evidence or {}),
                **dict(self.payload or {}),
            },
        )


__all__ = ["CANON_EFFECTOR_RESULT", "EffectorResult"]
