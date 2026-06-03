from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from execution.action_budget_engine import ActionBudgetDecision, ActionBudgetEngine
from execution.action_catalog import classify_action_type, normalize_action_type


CANON_BOUNDED_AUTONOMY = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


_DEFAULT_LIMITS: dict[str, dict[str, float | int]] = {
    "advisory": {
        "max_step_cost": 0.0,
        "max_run_cost": 0.0,
        "max_outbound_total": 0,
        "max_publications_total": 0,
        "max_irreversible_total": 0,
        "max_budget_change_total": 0.0,
        "max_steps_per_run": 0,
    },
    "supervised": {
        "max_step_cost": 10.0,
        "max_run_cost": 50.0,
        "max_outbound_total": 10,
        "max_publications_total": 2,
        "max_irreversible_total": 1,
        "max_budget_change_total": 25.0,
        "max_steps_per_run": 5,
    },
    "bounded_autonomy": {
        "max_step_cost": 25.0,
        "max_run_cost": 100.0,
        "max_outbound_total": 25,
        "max_publications_total": 5,
        "max_irreversible_total": 1,
        "max_budget_change_total": 50.0,
        "max_steps_per_run": 8,
    },
    "full_autonomy": {
        "max_step_cost": 100.0,
        "max_run_cost": 500.0,
        "max_outbound_total": 100,
        "max_publications_total": 20,
        "max_irreversible_total": 3,
        "max_budget_change_total": 250.0,
        "max_steps_per_run": 20,
    },
}


@dataclass(frozen=True)
class BoundedAutonomyDecision:
    allowed: bool
    operator_required: bool
    reason: str
    details: dict[str, Any]
    budget_decision: ActionBudgetDecision

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": bool(self.allowed),
            "operator_required": bool(self.operator_required),
            "reason": str(self.reason),
            "details": dict(self.details),
            "budget_decision": self.budget_decision.to_dict(),
        }


class BoundedAutonomyGuard:
    def __init__(self, *, action_budget_engine: ActionBudgetEngine | None = None) -> None:
        self._action_budget_engine = action_budget_engine or ActionBudgetEngine()

    def _tier(self, request: Any) -> str:
        tier = _text(getattr(request, "autonomy_tier", "supervised"), default="supervised")
        if tier not in _DEFAULT_LIMITS:
            return "supervised"
        return tier

    def _resolve_limit(self, *, request: Any, name: str, default: float | int) -> float | int:
        constraints = _safe_dict(getattr(request, "constraints", {}) or {})
        economy = _safe_dict(getattr(request, "economy", {}) or {})
        approval = _safe_dict(getattr(request, "approval_policy", {}) or {})
        bounded = _safe_dict(approval.get("bounded_autonomy") or {})
        if name in constraints and constraints[name] is not None:
            return constraints[name]
        if name in economy and economy[name] is not None:
            return economy[name]
        if name in bounded and bounded[name] is not None:
            return bounded[name]
        return default

    def evaluate(
        self,
        *,
        request: Any,
        action_type: str,
        payload: Mapping[str, Any] | None,
        previous_feedback: Mapping[str, Any] | None,
        budget_decision: ActionBudgetDecision | None = None,
    ) -> BoundedAutonomyDecision:
        tier = self._tier(request)
        normalized_action_type = normalize_action_type(action_type)
        action_class = classify_action_type(normalized_action_type)

        decision = budget_decision or self._action_budget_engine.evaluate(
            request=request,
            action_type=normalized_action_type,
            payload=payload,
            previous_feedback=previous_feedback,
        )
        if not decision.allowed:
            return BoundedAutonomyDecision(
                allowed=False,
                operator_required=True,
                reason="action_budget_exceeded",
                details={
                    "tier": tier,
                    "action_type": normalized_action_type,
                    "action_class": action_class,
                    "violated_limits": list(decision.violated_limits),
                },
                budget_decision=decision,
            )

        defaults = _DEFAULT_LIMITS[tier]
        after = decision.snapshot_after
        cost = decision.cost
        violations: list[str] = []

        max_step_cost = _safe_float(self._resolve_limit(request=request, name="max_step_cost", default=defaults["max_step_cost"]), default=float(defaults["max_step_cost"]))
        max_run_cost = _safe_float(self._resolve_limit(request=request, name="max_run_cost", default=defaults["max_run_cost"]), default=float(defaults["max_run_cost"]))
        max_outbound_total = _safe_int(self._resolve_limit(request=request, name="max_outbound_total", default=defaults["max_outbound_total"]), default=int(defaults["max_outbound_total"]))
        max_publications_total = _safe_int(self._resolve_limit(request=request, name="max_publications_total", default=defaults["max_publications_total"]), default=int(defaults["max_publications_total"]))
        max_irreversible_total = _safe_int(self._resolve_limit(request=request, name="max_irreversible_total", default=defaults["max_irreversible_total"]), default=int(defaults["max_irreversible_total"]))
        max_budget_change_total = _safe_float(self._resolve_limit(request=request, name="max_budget_change_total", default=defaults["max_budget_change_total"]), default=float(defaults["max_budget_change_total"]))
        max_steps_per_run = _safe_int(self._resolve_limit(request=request, name="max_steps_per_run", default=defaults["max_steps_per_run"]), default=int(defaults["max_steps_per_run"]))

        if max_step_cost >= 0.0 and cost.estimated_cost > max_step_cost:
            violations.append("max_step_cost")
        if max_run_cost >= 0.0 and after.spent_this_run > max_run_cost:
            violations.append("max_run_cost")
        if max_outbound_total >= 0 and after.outbound_total > max_outbound_total:
            violations.append("max_outbound_total")
        if max_publications_total >= 0 and after.publications_total > max_publications_total:
            violations.append("max_publications_total")
        if max_irreversible_total >= 0 and after.irreversible_total > max_irreversible_total:
            violations.append("max_irreversible_total")
        if max_budget_change_total >= 0.0 and after.budget_change_total > max_budget_change_total:
            violations.append("max_budget_change_total")
        if max_steps_per_run >= 0 and after.step_count > max_steps_per_run:
            violations.append("max_steps_per_run")

        approval = _safe_dict(getattr(request, "approval_policy", {}) or {})
        operator_on_budget_change = bool(approval.get("require_operator_on_budget_change", False))
        operator_on_irreversible = bool(approval.get("require_operator_on_irreversible", False))
        operator_required = False
        operator_reasons: list[str] = []

        if operator_on_budget_change and float(cost.budget_change_amount) > 0.0:
            operator_required = True
            operator_reasons.append("budget_change_requires_operator")
        if operator_on_irreversible and int(cost.irreversible_count) > 0:
            operator_required = True
            operator_reasons.append("irreversible_requires_operator")
        if tier == "supervised" and action_class in {"ads_write", "budget_change", "profile_publish", "unknown"}:
            operator_required = True
            operator_reasons.append("supervised_requires_operator")

        allowed = not violations and not operator_required and tier != "advisory"
        reason = "within_bounded_autonomy"
        if tier == "advisory":
            reason = "advisory_cannot_execute"
        elif violations:
            reason = "bounded_autonomy_exceeded"
        elif operator_required:
            reason = "bounded_autonomy_requires_operator"

        return BoundedAutonomyDecision(
            allowed=allowed,
            operator_required=operator_required,
            reason=reason,
            details={
                "tier": tier,
                "action_type": normalized_action_type,
                "action_class": action_class,
                "resolved_limits": {
                    "max_step_cost": max_step_cost,
                    "max_run_cost": max_run_cost,
                    "max_outbound_total": max_outbound_total,
                    "max_publications_total": max_publications_total,
                    "max_irreversible_total": max_irreversible_total,
                    "max_budget_change_total": max_budget_change_total,
                    "max_steps_per_run": max_steps_per_run,
                },
                "violated_limits": list(violations),
                "operator_reasons": operator_reasons,
            },
            budget_decision=decision,
        )


__all__ = [
    "CANON_BOUNDED_AUTONOMY",
    "BoundedAutonomyDecision",
    "BoundedAutonomyGuard",
]
