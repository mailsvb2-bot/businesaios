from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

CANON_AUTONOMY_RECOVERY_SEMANTICS = True

_SAFE_DENIAL_STATUSES = {"blocked_by_policy", "approval_required", "operator_required"}
_FAILURE_STATUSES = {"failed", "execution_failed", "verification_failed"}


@dataclass(frozen=True)
class RecoverySemantics:
    status: str
    is_failure: bool
    is_safe_denial: bool
    counts_toward_consecutive_failures: bool
    suggested_tier: str | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": str(self.status),
            "is_failure": bool(self.is_failure),
            "is_safe_denial": bool(self.is_safe_denial),
            "counts_toward_consecutive_failures": bool(self.counts_toward_consecutive_failures),
            "suggested_tier": self.suggested_tier,
            "reason": str(self.reason),
        }


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def classify_recovery_semantics(*, step: Any, safe_loop_decision: Mapping[str, Any] | None = None) -> RecoverySemantics:
    status = str(getattr(step, "status", "") or "")
    safe_loop = _safe_dict(safe_loop_decision)
    if bool(getattr(step, "verified", False)):
        return RecoverySemantics(status=status or "verified", is_failure=False, is_safe_denial=False, counts_toward_consecutive_failures=False, suggested_tier=safe_loop.get("next_tier") if safe_loop.get("should_downgrade") else None, reason="verified_success")
    if status in _SAFE_DENIAL_STATUSES or bool(getattr(step, "operator_required", False)):
        return RecoverySemantics(status=status or "operator_required", is_failure=False, is_safe_denial=True, counts_toward_consecutive_failures=False, suggested_tier=safe_loop.get("next_tier") if safe_loop.get("should_downgrade") else None, reason="policy_stop")
    if bool(getattr(step, "executed", False)) and not bool(getattr(step, "verified", False)):
        return RecoverySemantics(status=status or "verification_failed", is_failure=True, is_safe_denial=False, counts_toward_consecutive_failures=True, suggested_tier=safe_loop.get("next_tier") if safe_loop.get("should_downgrade") else None, reason="unverified_execution")
    return RecoverySemantics(status=status or "failed", is_failure=True, is_safe_denial=False, counts_toward_consecutive_failures=True, suggested_tier=safe_loop.get("next_tier") if safe_loop.get("should_downgrade") else None, reason="execution_failure")


__all__ = ["CANON_AUTONOMY_RECOVERY_SEMANTICS", "RecoverySemantics", "classify_recovery_semantics"]
