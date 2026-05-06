from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from execution.action_budget_engine import ActionBudgetDecision, ActionBudgetEngine
from governance.economic.action_economics_model import (
    ActionEconomicsIntent,
    ActionEconomicsSnapshot,
    build_assessment,
)
from governance.economic.economic_policy_contract import EconomicPolicyConfig, PolicyCheckResult
from governance.economic.spend_cap_policy import SpendCapPolicy


CANON_SPEND_LIMIT_POLICY = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


@dataclass(frozen=True, slots=True)
class SpendLimitPolicyDecision:
    allowed: bool
    operator_required: bool
    reason: str
    reasons: tuple[str, ...] = ()
    requested_budget: float = 0.0
    approved_budget: float = 0.0
    remaining_run_budget: float | None = None
    remaining_total_budget: float | None = None
    currency: str = "USD"
    spend_cap_check: dict[str, Any] = field(default_factory=dict)
    action_budget: dict[str, Any] = field(default_factory=dict)
    assessment: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": bool(self.allowed),
            "operator_required": bool(self.operator_required),
            "reason": self.reason,
            "reasons": list(self.reasons),
            "requested_budget": float(self.requested_budget),
            "approved_budget": float(self.approved_budget),
            "remaining_run_budget": self.remaining_run_budget,
            "remaining_total_budget": self.remaining_total_budget,
            "currency": self.currency,
            "spend_cap_check": dict(self.spend_cap_check),
            "action_budget": dict(self.action_budget),
            "assessment": dict(self.assessment),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class _DecisionAdapter:
    action: str
    payload: dict[str, Any]


def _economic_policy_config_from_sources(
    *,
    request: Any | None,
    world_state: Any | None,
    fallback: EconomicPolicyConfig | None,
) -> EconomicPolicyConfig:
    if fallback is not None:
        return fallback

    request_policy = _safe_dict(getattr(request, "economic_policy", {}))
    if request_policy:
        return EconomicPolicyConfig.from_mapping(request_policy)

    if isinstance(world_state, Mapping):
        world_state_dict = _safe_dict(world_state)
        world_policy = _safe_dict(world_state_dict.get("economic_policy"))
        if world_policy:
            return EconomicPolicyConfig.from_mapping(world_policy)
        economics_state = _safe_dict(world_state_dict.get("economics_state"))
    else:
        world_policy = _safe_dict(getattr(world_state, "economic_policy", {}))
        if world_policy:
            return EconomicPolicyConfig.from_mapping(world_policy)
        economics_state = _safe_dict(getattr(world_state, "economics_state", {}))

    economics_policy = _safe_dict(economics_state.get("economic_policy"))
    if economics_policy:
        return EconomicPolicyConfig.from_mapping(economics_policy)

    return EconomicPolicyConfig()


class SpendLimitPolicy:
    """
    Execution-facing normalization layer for spend limits.

    Important:
    - NOT a second economic brain.
    - Canonical spend-cap logic remains in governance.economic.spend_cap_policy.
    - Canonical per-run / cumulative budget accounting remains in execution.action_budget_engine.
    - This module only assembles a stable execution-level verdict and metadata.
    """

    def __init__(
        self,
        *,
        action_budget_engine: ActionBudgetEngine | None = None,
        economic_config: EconomicPolicyConfig | None = None,
    ) -> None:
        self._action_budget_engine = action_budget_engine or ActionBudgetEngine()
        self._economic_config = economic_config

    def evaluate(
        self,
        *,
        request: Any,
        action_type: str,
        payload: Mapping[str, Any] | None,
        world_state: Any | None = None,
        previous_feedback: Mapping[str, Any] | None = None,
        budget_decision: ActionBudgetDecision | None = None,
    ) -> SpendLimitPolicyDecision:
        config = _economic_policy_config_from_sources(
            request=request,
            world_state=world_state,
            fallback=self._economic_config,
        )
        action_payload = _safe_dict(payload)

        action_budget = budget_decision or self._action_budget_engine.evaluate(
            request=request,
            action_type=action_type,
            payload=action_payload,
            previous_feedback=previous_feedback,
        )

        decision = _DecisionAdapter(
            action=_text(action_type),
            payload={
                "action_type": _text(action_type),
                "channel": _text(action_payload.get("channel") or getattr(request, "channel", "headless")),
                "requested_budget": action_payload.get("requested_budget"),
                "priority": action_payload.get("priority"),
                "horizon_days": action_payload.get("horizon_days"),
                "economy": {
                    **_safe_dict(getattr(request, "economy", {})),
                    **_safe_dict(action_payload.get("economy")),
                    "requested_budget": (
                        action_payload.get("requested_budget")
                        if action_payload.get("requested_budget") is not None
                        else _safe_dict(action_payload.get("economy")).get("requested_budget")
                    ),
                },
            },
        )

        snapshot = ActionEconomicsSnapshot.from_sources(
            decision=decision,
            world_state=world_state,
            config=config,
        )
        intent = ActionEconomicsIntent.from_decision(decision, config=config)
        assessment = build_assessment(intent, snapshot)
        spend_cap_check = SpendCapPolicy(config=config).evaluate(
            intent=intent,
            snapshot=snapshot,
            assessment=assessment,
        )

        remaining_run_budget, remaining_total_budget = self._remaining_budgets(
            request=request,
            action_budget=action_budget,
        )
        approved_budget = self._approved_budget(
            requested_budget=assessment.requested_budget,
            spend_cap_check=spend_cap_check,
            remaining_run_budget=remaining_run_budget,
            remaining_total_budget=remaining_total_budget,
        )

        allowed = bool(action_budget.allowed and not spend_cap_check.is_veto())
        operator_required = bool(allowed and spend_cap_check.is_review())

        reasons: list[str] = []
        if not action_budget.allowed:
            reasons.extend(f"action_budget:{token}" for token in action_budget.violated_limits)
        if spend_cap_check.reason:
            reasons.append(spend_cap_check.reason)
        if not reasons:
            reasons.append("spend_limit_allow")

        if not action_budget.allowed:
            reason = "action_budget_exceeded"
        elif spend_cap_check.is_veto():
            reason = spend_cap_check.reason
        elif spend_cap_check.is_review():
            reason = spend_cap_check.reason
        else:
            reason = "spend_limit_allow"

        return SpendLimitPolicyDecision(
            allowed=allowed,
            operator_required=operator_required,
            reason=reason,
            reasons=tuple(dict.fromkeys(item for item in reasons if _text(item))),
            requested_budget=float(assessment.requested_budget),
            approved_budget=float(approved_budget),
            remaining_run_budget=remaining_run_budget,
            remaining_total_budget=remaining_total_budget,
            currency=str(action_budget.snapshot_after.currency or "USD"),
            spend_cap_check=self._policy_check_to_dict(spend_cap_check),
            action_budget=action_budget.to_dict(),
            assessment={
                "requested_budget": float(assessment.requested_budget),
                "total_encumbrance": float(assessment.total_encumbrance),
                "cash_after_action": float(assessment.cash_after_action),
                "liquidity_after_action": float(assessment.liquidity_after_action),
                "reserve_gap": float(assessment.reserve_gap),
                "runway_days_after_action": float(assessment.runway_days_after_action),
                "expected_roi": float(assessment.expected_roi),
                "expected_margin_after_action": float(assessment.expected_margin_after_action),
            },
            metadata={
                "channel": intent.channel,
                "action_type": intent.action_type,
                "policy_owner": "governance.economic.spend_cap_policy",
                "budget_owner": "execution.action_budget_engine",
                "spend_cap_status": spend_cap_check.status,
                "configured_currency": config.currency,
                "used_precomputed_budget_decision": budget_decision is not None,
                "requested_budget_source": (
                    "payload"
                    if action_payload.get("requested_budget") is not None
                    else "payload.economy/request.economy"
                ),
            },
        )

    @staticmethod
    def _policy_check_to_dict(check: PolicyCheckResult) -> dict[str, Any]:
        return {
            "policy_name": check.policy_name,
            "status": check.status,
            "reason": check.reason,
            "details": dict(check.details),
        }

    @staticmethod
    def _remaining_budgets(
        *,
        request: Any,
        action_budget: ActionBudgetDecision,
    ) -> tuple[float | None, float | None]:
        economy = _safe_dict(getattr(request, "economy", {}))
        constraints = _safe_dict(getattr(request, "constraints", {}))

        max_run_cost = _safe_float(
            economy.get("max_run_cost") or economy.get("run_budget") or constraints.get("max_run_cost"),
            default=0.0,
        )
        max_total_cost = _safe_float(
            economy.get("max_total_cost") or economy.get("total_budget") or constraints.get("max_total_cost"),
            default=0.0,
        )

        remaining_run_budget = None
        remaining_total_budget = None

        if max_run_cost > 0.0:
            remaining_run_budget = max(
                0.0,
                max_run_cost - float(action_budget.snapshot_after.spent_this_run),
            )
        if max_total_cost > 0.0:
            remaining_total_budget = max(
                0.0,
                max_total_cost - float(action_budget.snapshot_after.spent_total),
            )

        return remaining_run_budget, remaining_total_budget

    @staticmethod
    def _approved_budget(
        *,
        requested_budget: float,
        spend_cap_check: PolicyCheckResult,
        remaining_run_budget: float | None,
        remaining_total_budget: float | None,
    ) -> float:
        approved = max(0.0, float(requested_budget))

        hard_cap = _safe_float(spend_cap_check.details.get("hard_cap"), default=0.0)
        if hard_cap > 0.0:
            approved = min(approved, hard_cap)

        if remaining_run_budget is not None:
            approved = min(approved, remaining_run_budget)

        if remaining_total_budget is not None:
            approved = min(approved, remaining_total_budget)

        return max(0.0, approved)


__all__ = [
    "CANON_SPEND_LIMIT_POLICY",
    "SpendLimitPolicy",
    "SpendLimitPolicyDecision",
]
