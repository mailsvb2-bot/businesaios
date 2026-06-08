from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CANON_ACTION_RESULT = True


@dataclass(frozen=True)
class ActionResult:
    action_id: str
    status: str
    message: str = ''
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def attempted(self) -> bool:
        payload = dict(self.payload or {})
        if "attempted" in payload:
            return bool(payload.get("attempted"))
        return self.status not in {"blocked_by_policy", "approval_required"}

    @property
    def executed(self) -> bool:
        payload = dict(self.payload or {})
        if "executed" in payload:
            return bool(payload.get("executed"))
        return self.status in {"accepted", "executed", "verified"}

    @property
    def verified(self) -> bool:
        payload = dict(self.payload or {})
        if "verified" in payload:
            return bool(payload.get("verified"))
        effector = payload.get("effector")
        if isinstance(effector, dict) and "verified" in effector:
            return bool(effector.get("verified"))
        return self.status == "verified"

    @property
    def operator_required(self) -> bool:
        payload = dict(self.payload or {})
        if "operator_required" in payload:
            return bool(payload.get("operator_required"))
        effector = payload.get("effector")
        if isinstance(effector, dict) and "operator_required" in effector:
            return bool(effector.get("operator_required"))
        return self.status in {"operator_required", "approval_required", "blocked_by_policy"}

    @property
    def accepted(self) -> bool:
        """Backward-compatible alias.

        Canonical headless semantics should use attempted/executed/verified instead.
        """
        return self.executed

    def as_dict(self) -> dict[str, Any]:
        return {
            'action_id': self.action_id,
            'status': self.status,
            'message': self.message,
            'payload': dict(self.payload),
            'attempted': self.attempted,
            'executed': self.executed,
            'verified': self.verified,
            'operator_required': self.operator_required,
        }

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]
