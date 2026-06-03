from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping


CANON_SAFE_SELF_DRIVING = True

_TIER_ORDER = {
    "advisory": 0,
    "supervised": 1,
    "bounded_autonomy": 2,
    "full_autonomy": 3,
}


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _tier(value: object, *, default: str = "supervised") -> str:
    text = str(value or "").strip()
    return text if text in _TIER_ORDER else default


def _downgrade_tier(value: str) -> str:
    tier = _tier(value)
    if tier == "full_autonomy":
        return "bounded_autonomy"
    if tier == "bounded_autonomy":
        return "supervised"
    if tier == "supervised":
        return "advisory"
    return "advisory"


@dataclass(frozen=True)
class SafeSelfDrivingDecision:
    should_stop: bool
    should_downgrade: bool
    next_tier: str
    reason: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_stop": bool(self.should_stop),
            "should_downgrade": bool(self.should_downgrade),
            "next_tier": str(self.next_tier),
            "reason": str(self.reason),
            "details": dict(self.details),
        }


class SafeSelfDrivingPolicy:
    @staticmethod
    def _count_consecutive(steps: list[Any], *, predicate: Any) -> int:
        count = 0
        for step in reversed(list(steps)):
            if bool(predicate(step)):
                count += 1
            else:
                break
        return count

    def evaluate(
        self,
        *,
        request: Any,
        steps: list[Any],
        previous_feedback: Mapping[str, Any] | None,
        last_step: Any,
        consecutive_failures: int,
    ) -> SafeSelfDrivingDecision:
        constraints = _safe_dict(getattr(request, "constraints", {}) or {})
        current_tier = _tier(getattr(request, "autonomy_tier", "supervised"))

        max_consecutive_unverified = _safe_int(constraints.get("safe_loop_max_consecutive_unverified"), default=2)
        max_consecutive_operator_handoffs = _safe_int(constraints.get("safe_loop_max_consecutive_operator_handoffs"), default=2)
        max_consecutive_policy_denials = _safe_int(constraints.get("safe_loop_max_consecutive_policy_denials"), default=2)
        max_consecutive_failures = _safe_int(constraints.get("safe_loop_max_consecutive_failures"), default=3)

        consecutive_unverified = self._count_consecutive(
            steps,
            predicate=lambda step: bool(getattr(step, "executed", False)) and not bool(getattr(step, "verified", False)),
        )
        consecutive_operator_handoffs = self._count_consecutive(
            steps,
            predicate=lambda step: bool(getattr(step, "operator_required", False)),
        )
        consecutive_policy_denials = self._count_consecutive(
            steps,
            predicate=lambda step: str(getattr(step, "status", "") or "") in {"blocked_by_policy", "approval_required", "operator_required"},
        )

        details = {
            "current_tier": current_tier,
            "consecutive_unverified": consecutive_unverified,
            "consecutive_operator_handoffs": consecutive_operator_handoffs,
            "consecutive_policy_denials": consecutive_policy_denials,
            "consecutive_failures": int(consecutive_failures),
            "last_step_status": str(getattr(last_step, "status", "") or ""),
        }

        if consecutive_operator_handoffs >= max_consecutive_operator_handoffs:
            next_tier = _downgrade_tier(current_tier)
            should_stop = _TIER_ORDER[current_tier] <= _TIER_ORDER["supervised"]
            return SafeSelfDrivingDecision(should_stop=should_stop, should_downgrade=not should_stop and next_tier != current_tier, next_tier=next_tier, reason="safe_loop_operator_handoff_limit", details=details)
        if consecutive_policy_denials >= max_consecutive_policy_denials:
            next_tier = _downgrade_tier(current_tier)
            should_stop = _TIER_ORDER[current_tier] <= _TIER_ORDER["supervised"]
            return SafeSelfDrivingDecision(should_stop=should_stop, should_downgrade=not should_stop and next_tier != current_tier, next_tier=next_tier, reason="safe_loop_policy_denial_limit", details=details)
        if consecutive_unverified >= max_consecutive_unverified:
            next_tier = _downgrade_tier(current_tier)
            should_stop = _TIER_ORDER[current_tier] <= _TIER_ORDER["bounded_autonomy"]
            return SafeSelfDrivingDecision(should_stop=should_stop, should_downgrade=not should_stop and next_tier != current_tier, next_tier=next_tier, reason="safe_loop_unverified_limit", details=details)
        if int(consecutive_failures) >= max_consecutive_failures:
            next_tier = _downgrade_tier(current_tier)
            should_stop = _TIER_ORDER[current_tier] <= _TIER_ORDER["supervised"]
            return SafeSelfDrivingDecision(should_stop=should_stop, should_downgrade=not should_stop and next_tier != current_tier, next_tier=next_tier, reason="safe_loop_failure_limit", details=details)

        return SafeSelfDrivingDecision(
            should_stop=False,
            should_downgrade=False,
            next_tier=current_tier,
            reason="safe_loop_continue",
            details=details,
        )


__all__ = [
    "CANON_SAFE_SELF_DRIVING",
    "SafeSelfDrivingDecision",
    "SafeSelfDrivingPolicy",
]
