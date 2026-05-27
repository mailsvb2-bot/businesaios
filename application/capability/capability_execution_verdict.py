from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from application.autonomy.autonomy_tiers import evaluate_autonomy_tier
from execution.action_budget_engine import ActionBudgetEngine
from execution.blast_radius_guard import BlastRadiusGuard
from execution.operational_budget import BudgetWindowUsage, OperationalBudget, OperationalBudgetGuard

CANON_CAPABILITY_EXECUTION_VERDICT = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


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


def _text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class CapabilityExecutionVerdict:
    allowed: bool
    reason: str
    approval_required: bool
    budget_allowed: bool
    blast_radius_allowed: bool
    blocked_by_policy: bool
    operator_required: bool
    autonomy_tier: str
    recommended_action_type: str | None = None
    approval: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)
    operational_budget: dict[str, Any] = field(default_factory=dict)
    blast_radius: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": bool(self.allowed),
            "reason": str(self.reason),
            "approval_required": bool(self.approval_required),
            "budget_allowed": bool(self.budget_allowed),
            "blast_radius_allowed": bool(self.blast_radius_allowed),
            "blocked_by_policy": bool(self.blocked_by_policy),
            "operator_required": bool(self.operator_required),
            "autonomy_tier": str(self.autonomy_tier),
            "recommended_action_type": self.recommended_action_type,
            "approval": dict(self.approval),
            "budget": dict(self.budget),
            "operational_budget": dict(self.operational_budget),
            "blast_radius": dict(self.blast_radius),
        }


class CapabilityExecutionVerdictBuilder:
    """
    Advisory preflight aggregator.

    It does not create a second decision path. It only materializes a single,
    canonical execution verdict around an already-selected action.
    """

    def __init__(
        self,
        *,
        action_budget_engine: ActionBudgetEngine | None = None,
        blast_radius_guard: BlastRadiusGuard | None = None,
        operational_budget_guard: OperationalBudgetGuard | None = None,
    ) -> None:
        self._action_budget_engine = action_budget_engine or ActionBudgetEngine()
        self._blast_radius_guard = blast_radius_guard or BlastRadiusGuard(action_budget_engine=self._action_budget_engine)
        self._operational_budget_guard = operational_budget_guard or OperationalBudgetGuard()

    def _build_operational_budget(self, *, request: Any, payload: Mapping[str, Any]) -> tuple[OperationalBudget, BudgetWindowUsage, BudgetWindowUsage]:
        constraints = _safe_dict(getattr(request, "constraints", {}) or {})
        operational_payload = {
            "max_actions_per_hour": constraints.get("operational_budget_max_actions_per_hour", constraints.get("max_actions_per_hour", 25)),
            "max_actions_per_day": constraints.get("operational_budget_max_actions_per_day", constraints.get("max_actions_per_day", 100)),
            "max_outbound_per_window": constraints.get("operational_budget_max_outbound_per_window", constraints.get("max_outbound_per_window", 20)),
            "max_new_assets_per_day": constraints.get("operational_budget_max_new_assets_per_day", constraints.get("max_new_assets_per_day", 10)),
            "max_irreversible_actions_per_window": constraints.get("operational_budget_max_irreversible_actions_per_window", constraints.get("max_irreversible_actions_per_window", 2)),
            "max_budget_change_per_window": constraints.get("operational_budget_max_budget_change_per_window", constraints.get("max_budget_change_per_window")),
        }
        budget = OperationalBudget.from_constraints(operational_payload)
        persistent_counters = _safe_dict(payload.get("persistent_counters") or {})
        hour_usage = BudgetWindowUsage(
            actions=max(0, _safe_int(persistent_counters.get("actions_hour"))),
            outbound=max(0, _safe_int(persistent_counters.get("outbound_total"))),
            new_assets=max(0, _safe_int(persistent_counters.get("publication_total"))),
            irreversible_actions=max(0, _safe_int(persistent_counters.get("irreversible_total"))),
            budget_change_amount=max(0.0, _safe_float(persistent_counters.get("budget_change_total"))),
        )
        day_usage = BudgetWindowUsage(
            actions=max(0, _safe_int(persistent_counters.get("actions_day"))),
            outbound=max(0, _safe_int(persistent_counters.get("outbound_total"))),
            new_assets=max(0, _safe_int(persistent_counters.get("publication_total"))),
            irreversible_actions=max(0, _safe_int(persistent_counters.get("irreversible_total"))),
            budget_change_amount=max(0.0, _safe_float(persistent_counters.get("budget_change_total"))),
        )
        return budget, hour_usage, day_usage

    def build(
        self,
        *,
        request: Any,
        action_type: str,
        payload: Mapping[str, Any] | None,
        capability_allowed: bool,
        fallback_action_type: str | None = None,
        policy_verdict: Mapping[str, Any] | None = None,
    ) -> CapabilityExecutionVerdict:
        payload_dict = _safe_dict(payload)
        autonomy_tier = _text(getattr(request, "autonomy_tier", "supervised") or "supervised") or "supervised"
        approval_policy = dict(getattr(request, "approval_policy", {}) or {})
        approval_decision = evaluate_autonomy_tier(
            action_type=action_type,
            autonomy_tier=autonomy_tier,
            approval_policy=approval_policy,
        )
        previous_feedback = _safe_dict(payload_dict.get("previous_feedback") or _safe_dict(getattr(request, "meta", {})).get("previous_feedback"))
        budget_decision = self._action_budget_engine.evaluate(
            request=request,
            action_type=action_type,
            payload=payload_dict,
            previous_feedback=previous_feedback,
        )
        blast_decision = self._blast_radius_guard.evaluate(
            request=request,
            action_type=action_type,
            payload=payload_dict,
            tenant_id=_text(getattr(request, "tenant_id", "default") or payload_dict.get("tenant_id") or "default"),
            autonomy_tier=autonomy_tier,
            recent_actions=list(payload_dict.get("recent_actions") or []),
        )
        operational_budget, hour_usage, day_usage = self._build_operational_budget(request=request, payload=payload_dict)
        cost = budget_decision.cost.to_dict()
        proposed_action_cost = {
            "actions": 1,
            "outbound": int(cost.get("outbound_count", 0)),
            "new_assets": int(cost.get("publication_count", 0)),
            "irreversible_actions": int(cost.get("irreversible_count", 0)),
            "budget_change_amount": float(cost.get("budget_change_amount", 0.0)),
        }
        operational_budget_decision = self._operational_budget_guard.evaluate(
            budget=operational_budget,
            hour_usage=hour_usage,
            day_usage=day_usage,
            proposed_action_cost=proposed_action_cost,
        )

        policy_verdict_dict = _safe_dict(policy_verdict)
        blocked_by_policy = bool(approval_decision.blocked_by_policy or policy_verdict_dict.get("allowed") is False)
        approval_required = bool(
            approval_decision.approval_required
            or payload_dict.get("approval_required")
            or policy_verdict_dict.get("operator_required")
        )
        budget_allowed = bool(budget_decision.allowed and operational_budget_decision.allowed)
        blast_radius_allowed = bool(blast_decision.allowed)
        operator_required = bool(approval_required or blocked_by_policy or not budget_allowed or not blast_radius_allowed)
        allowed = bool(capability_allowed and not operator_required)

        policy_reason = _text(policy_verdict_dict.get("reason"))
        if not capability_allowed:
            reason = policy_reason or "capability_preflight_denied"
        elif blocked_by_policy:
            reason = policy_reason or approval_decision.handoff_reason or "blocked_by_policy"
        elif approval_required:
            reason = approval_decision.handoff_reason or "approval_required"
        elif not budget_decision.allowed:
            reason = str(budget_decision.reason)
        elif not operational_budget_decision.allowed:
            reason = str(operational_budget_decision.reason)
        elif not blast_decision.allowed:
            reason = str(blast_decision.reason or "blast_radius_exceeded")
        else:
            reason = "within_execution_verdict"

        return CapabilityExecutionVerdict(
            allowed=allowed,
            reason=reason,
            approval_required=approval_required,
            budget_allowed=budget_allowed,
            blast_radius_allowed=blast_radius_allowed,
            blocked_by_policy=blocked_by_policy,
            operator_required=operator_required,
            autonomy_tier=autonomy_tier,
            recommended_action_type=fallback_action_type,
            approval={
                "allowed": bool(approval_decision.allowed and not blocked_by_policy),
                "approval_required": bool(approval_required),
                "blocked_by_policy": bool(blocked_by_policy),
                "handoff_reason": policy_reason or approval_decision.handoff_reason,
                "action_class": str(approval_decision.action_class),
                "policy_scope": _text(policy_verdict_dict.get("policy_scope")) or None,
                "recommended_autonomy_tier": _text(policy_verdict_dict.get("recommended_autonomy_tier")) or None,
            },
            budget=budget_decision.to_dict(),
            operational_budget=operational_budget_decision.to_dict(),
            blast_radius={
                "allowed": bool(blast_decision.allowed),
                "reason": blast_decision.reason,
                "details": dict(blast_decision.details or {}),
            },
        )


__all__ = [
    "CANON_CAPABILITY_EXECUTION_VERDICT",
    "CapabilityExecutionVerdict",
    "CapabilityExecutionVerdictBuilder",
]
