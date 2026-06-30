from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from execution.action_budget_engine import ActionBudgetEngine
from execution.action_cost_model import ActionCostModel
from execution.economic_signal_context import EconomicSignalContextBuilder
from execution.economic_risk_envelope import EconomicRiskEnvelopeBuilder
from execution.operational_budget import (
    BudgetWindowUsage,
    OperationalBudget,
    OperationalBudgetGuard,
)
from execution.revenue_verification import (
    RevenueVerification,
    RevenueVerificationExpectation,
    RevenueVerificationResult,
)
from execution.spend_limit_policy import SpendLimitPolicy
from execution.economic_policy_snapshot import EconomicPolicySnapshotBuilder
from governance.economic.economic_policy_contract import EconomicPolicyConfig
from governance.economic.economic_policy_engine import EconomicPolicyEngine


CANON_BUDGET_GUARD = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


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


@dataclass(frozen=True, slots=True)
class BudgetGuardDecision:
    allowed: bool
    operator_required: bool
    reason: str
    reasons: tuple[str, ...] = ()
    action_budget: dict[str, Any] = field(default_factory=dict)
    operational_budget: dict[str, Any] = field(default_factory=dict)
    spend_limits: dict[str, Any] = field(default_factory=dict)
    economic_policy: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": bool(self.allowed),
            "operator_required": bool(self.operator_required),
            "reason": self.reason,
            "reasons": list(self.reasons),
            "action_budget": dict(self.action_budget),
            "operational_budget": dict(self.operational_budget),
            "spend_limits": dict(self.spend_limits),
            "economic_policy": dict(self.economic_policy),
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


class BudgetGuard:
    """
    Canonical execution-facing budget guard.

    Important:
    - This is an aggregation layer, not an alternative decision core.
    - Economic veto logic remains owned by governance.economic.economic_policy_engine.
    - Action spend accounting remains owned by execution.action_budget_engine.
    - Window/rate budget checks remain owned by execution.operational_budget.
    - Optional revenue confirmation remains owned by execution.revenue_verification.
    """

    def __init__(
        self,
        *,
        action_budget_engine: ActionBudgetEngine | None = None,
        spend_limit_policy: SpendLimitPolicy | None = None,
        operational_budget_guard: OperationalBudgetGuard | None = None,
        economic_policy_engine: EconomicPolicyEngine | None = None,
        revenue_verification: RevenueVerification | None = None,
        economic_config: EconomicPolicyConfig | None = None,
    ) -> None:
        self._economic_config = economic_config
        self._action_budget_engine = action_budget_engine or ActionBudgetEngine()
        self._spend_limit_policy = spend_limit_policy or SpendLimitPolicy(
            action_budget_engine=self._action_budget_engine,
            economic_config=economic_config,
        )
        self._operational_budget_guard = operational_budget_guard or OperationalBudgetGuard()
        self._economic_policy_engine = economic_policy_engine
        self._revenue_verification = revenue_verification or RevenueVerification()
        self._action_cost_model = ActionCostModel()
        self._economic_signal_context = EconomicSignalContextBuilder(config=economic_config)
        self._risk_envelope_builder = EconomicRiskEnvelopeBuilder()
        self._policy_snapshot_builder = EconomicPolicySnapshotBuilder()

    def evaluate(
        self,
        *,
        request: Any,
        action_type: str,
        payload: Mapping[str, Any] | None,
        previous_feedback: Mapping[str, Any] | None = None,
        world_state: Any | None = None,
        hour_usage: Mapping[str, Any] | BudgetWindowUsage | None = None,
        day_usage: Mapping[str, Any] | BudgetWindowUsage | None = None,
    ) -> BudgetGuardDecision:
        config = _economic_policy_config_from_sources(
            request=request,
            world_state=world_state,
            fallback=self._economic_config,
        )
        economic_policy_engine = self._economic_policy_engine or EconomicPolicyEngine(config=config)

        action_payload = _safe_dict(payload)

        budget_decision = self._action_budget_engine.evaluate(
            request=request,
            action_type=action_type,
            payload=action_payload,
            previous_feedback=previous_feedback,
        )

        spend_limits = self._spend_limit_policy.evaluate(
            request=request,
            action_type=action_type,
            payload=action_payload,
            world_state=world_state,
            previous_feedback=previous_feedback,
            budget_decision=budget_decision,
        )

        operational_budget, resolved_hour_usage, resolved_day_usage = self._build_operational_budget(
            request=request,
            payload=action_payload,
            hour_usage=hour_usage,
            day_usage=day_usage,
        )
        proposed_action_cost = {
            "actions": 1,
            "outbound": int(budget_decision.cost.outbound_count),
            "new_assets": int(budget_decision.cost.publication_count),
            "irreversible_actions": int(budget_decision.cost.irreversible_count),
            "budget_change_amount": float(budget_decision.cost.budget_change_amount),
        }
        operational_decision = self._operational_budget_guard.evaluate(
            budget=operational_budget,
            hour_usage=resolved_hour_usage,
            day_usage=resolved_day_usage,
            proposed_action_cost=proposed_action_cost,
        )

        decision_like = self._build_decision_adapter(
            request=request,
            action_type=action_type,
            payload=action_payload,
        )
        economic_verdict = economic_policy_engine.review(decision_like, world_state or {})
        canonical_cost = self._action_cost_model.from_sources(
            action_type=action_type,
            payload=action_payload,
            request=request,
            budget_decision=budget_decision,
        )
        planning_signals = self._economic_signal_context.build(
            decision_like=decision_like,
            world_state=world_state,
            economic_verdict=economic_verdict,
        )
        risk_envelope = self._risk_envelope_builder.build(
            planning_signals=planning_signals.to_decision_context(),
            spend_limits=spend_limits.to_dict(),
            economic_policy={
                "allowed": bool(getattr(economic_verdict, "allowed", False)),
                "operator_required": bool(getattr(economic_verdict, "operator_required", False)),
                "reason": str(getattr(economic_verdict, "reason", "")),
                "survival_mode": str(getattr(economic_verdict, "survival_mode", "normal")),
            },
        )

        allowed = bool(
            budget_decision.allowed
            and spend_limits.allowed
            and operational_decision.allowed
            and economic_verdict.allowed
        )
        operator_required = bool(
            allowed
            and (
                spend_limits.operator_required
                or bool(getattr(economic_verdict, "operator_required", False))
            )
        )

        reasons: list[str] = []
        if not budget_decision.allowed:
            reasons.extend(f"action_budget:{item}" for item in budget_decision.violated_limits)
        if not operational_decision.allowed:
            reasons.extend(f"operational_budget:{item}" for item in operational_decision.violated_rules)
        reasons.extend(spend_limits.reasons)
        reasons.extend(tuple(getattr(economic_verdict, "reasons", ()) or ()))

        if not reasons:
            reasons.append("budget_guard_allow")

        if not budget_decision.allowed:
            reason = "action_budget_exceeded"
        elif not operational_decision.allowed:
            reason = "operational_budget_exceeded"
        elif not spend_limits.allowed:
            reason = spend_limits.reason
        elif not economic_verdict.allowed:
            reason = str(getattr(economic_verdict, "reason", "economic_policy_veto"))
        elif operator_required:
            reason = (
                spend_limits.reason
                if spend_limits.operator_required
                else str(getattr(economic_verdict, "reason", "economic_operator_review"))
            )
        else:
            reason = "budget_guard_allow"

        return BudgetGuardDecision(
            allowed=allowed,
            operator_required=operator_required,
            reason=reason,
            reasons=tuple(dict.fromkeys(item for item in reasons if _text(item))),
            action_budget=budget_decision.to_dict(),
            operational_budget=operational_decision.to_dict(),
            spend_limits=spend_limits.to_dict(),
            economic_policy={
                "allowed": bool(getattr(economic_verdict, "allowed", False)),
                "operator_required": bool(getattr(economic_verdict, "operator_required", False)),
                "reason": str(getattr(economic_verdict, "reason", "")),
                "reasons": list(getattr(economic_verdict, "reasons", ()) or ()),
                "survival_mode": str(getattr(economic_verdict, "survival_mode", "normal")),
                "portfolio_allocation": dict(getattr(economic_verdict, "portfolio_allocation", {}) or {}),
                "metadata": dict(getattr(economic_verdict, "metadata", {}) or {}),
            },
            metadata={
                "action_type": _text(action_type),
                "channel": _text(action_payload.get("channel") or getattr(request, "channel", "headless")),
                "currency": budget_decision.snapshot_after.currency,
                "owners": {
                    "action_budget": "execution.action_budget_engine",
                    "operational_budget": "execution.operational_budget",
                    "spend_limits": "execution.spend_limit_policy -> governance.economic.spend_cap_policy",
                    "economic_policy": "governance.economic.economic_policy_engine",
                    "revenue_verification": "execution.revenue_verification",
                    "action_cost_model": "execution.action_cost_model",
                    "economic_signal_context": "execution.economic_signal_context",
                },
                "configured_currency": config.currency,
                "canonical_action_cost": canonical_cost.to_dict(),
                "planning_signals": planning_signals.to_decision_context(),
                "economic_confidence": planning_signals.economic_confidence,
                "suggested_survival_mode": planning_signals.suggested_survival_mode,
                "risk_envelope": risk_envelope.to_dict(),
                "policy_snapshot": self._policy_snapshot_builder.build(
                    snapshot_id=f"{_text(action_type)}::{_text(action_payload.get('channel') or getattr(request, 'channel', 'headless'))}",
                    budget_guard_result={
                        "allowed": allowed,
                        "operator_required": operator_required,
                        "reason": reason,
                        "spend_limits": spend_limits.to_dict(),
                        "economic_policy": {
                            "allowed": bool(getattr(economic_verdict, "allowed", False)),
                            "operator_required": bool(getattr(economic_verdict, "operator_required", False)),
                            "reason": str(getattr(economic_verdict, "reason", "")),
                            "reasons": list(getattr(economic_verdict, "reasons", ()) or ()),
                            "survival_mode": str(getattr(economic_verdict, "survival_mode", "normal")),
                        },
                        "metadata": {
                            "action_type": _text(action_type),
                            "channel": _text(action_payload.get("channel") or getattr(request, "channel", "headless")),
                            "planning_signals": planning_signals.to_decision_context(),
                            "risk_envelope": risk_envelope.to_dict(),
                        },
                    },
                ).to_dict(),
            },
        )

    def verify_revenue_outcome(
        self,
        *,
        action_type: str,
        feedback: Mapping[str, Any] | None,
        action_result: Any | None = None,
        expectation: RevenueVerificationExpectation | None = None,
    ) -> RevenueVerificationResult:
        return self._revenue_verification.verify(
            action_type=action_type,
            feedback=feedback,
            action_result=action_result,
            expectation=expectation,
        )

    def _build_operational_budget(
        self,
        *,
        request: Any,
        payload: Mapping[str, Any],
        hour_usage: Mapping[str, Any] | BudgetWindowUsage | None,
        day_usage: Mapping[str, Any] | BudgetWindowUsage | None,
    ) -> tuple[OperationalBudget, BudgetWindowUsage, BudgetWindowUsage]:
        constraints = _safe_dict(getattr(request, "constraints", {}) or {})
        operational_payload = {
            "max_actions_per_hour": constraints.get(
                "operational_budget_max_actions_per_hour",
                constraints.get("max_actions_per_hour", 25),
            ),
            "max_actions_per_day": constraints.get(
                "operational_budget_max_actions_per_day",
                constraints.get("max_actions_per_day", 100),
            ),
            "max_outbound_per_window": constraints.get(
                "operational_budget_max_outbound_per_window",
                constraints.get("max_outbound_per_window", 20),
            ),
            "max_new_assets_per_day": constraints.get(
                "operational_budget_max_new_assets_per_day",
                constraints.get("max_new_assets_per_day", 10),
            ),
            "max_irreversible_actions_per_window": constraints.get(
                "operational_budget_max_irreversible_actions_per_window",
                constraints.get("max_irreversible_actions_per_window", 2),
            ),
            "max_budget_change_per_window": constraints.get(
                "operational_budget_max_budget_change_per_window",
                constraints.get("max_budget_change_per_window"),
            ),
        }
        budget = OperationalBudget.from_constraints(operational_payload)

        if hour_usage is not None or day_usage is not None:
            return (
                budget,
                self._normalize_usage(hour_usage),
                self._normalize_usage(day_usage),
            )

        persistent_counters = _safe_dict(payload.get("persistent_counters") or {})
        resolved_hour_usage = BudgetWindowUsage(
            actions=max(0, _safe_int(persistent_counters.get("actions_hour"))),
            outbound=max(0, _safe_int(persistent_counters.get("outbound_total"))),
            new_assets=max(0, _safe_int(persistent_counters.get("publication_total"))),
            irreversible_actions=max(0, _safe_int(persistent_counters.get("irreversible_total"))),
            budget_change_amount=max(0.0, _safe_float(persistent_counters.get("budget_change_total"))),
        )
        resolved_day_usage = BudgetWindowUsage(
            actions=max(0, _safe_int(persistent_counters.get("actions_day"))),
            outbound=max(0, _safe_int(persistent_counters.get("outbound_total"))),
            new_assets=max(0, _safe_int(persistent_counters.get("publication_total"))),
            irreversible_actions=max(0, _safe_int(persistent_counters.get("irreversible_total"))),
            budget_change_amount=max(0.0, _safe_float(persistent_counters.get("budget_change_total"))),
        )
        return budget, resolved_hour_usage, resolved_day_usage

    @staticmethod
    def _normalize_usage(value: Mapping[str, Any] | BudgetWindowUsage | None) -> BudgetWindowUsage:
        if isinstance(value, BudgetWindowUsage):
            return value
        payload = _safe_dict(value)
        return BudgetWindowUsage(
            actions=max(0, _safe_int(payload.get("actions"), default=0)),
            outbound=max(0, _safe_int(payload.get("outbound"), default=0)),
            new_assets=max(0, _safe_int(payload.get("new_assets"), default=0)),
            irreversible_actions=max(0, _safe_int(payload.get("irreversible_actions"), default=0)),
            budget_change_amount=max(0.0, _safe_float(payload.get("budget_change_amount"), default=0.0)),
        )

    @staticmethod
    def _build_decision_adapter(
        *,
        request: Any,
        action_type: str,
        payload: Mapping[str, Any],
    ) -> _DecisionAdapter:
        request_economy = _safe_dict(getattr(request, "economy", {}))
        payload_economy = _safe_dict(payload.get("economy"))
        requested_budget = (
            payload.get("requested_budget")
            if payload.get("requested_budget") is not None
            else payload_economy.get("requested_budget")
        )

        return _DecisionAdapter(
            action=_text(action_type),
            payload={
                "action_type": _text(action_type),
                "channel": _text(payload.get("channel") or getattr(request, "channel", "headless")),
                "priority": payload.get("priority"),
                "horizon_days": payload.get("horizon_days"),
                "economy": {
                    **request_economy,
                    **payload_economy,
                    "requested_budget": requested_budget,
                },
            },
        )


__all__ = [
    "CANON_BUDGET_GUARD",
    "BudgetGuard",
    "BudgetGuardDecision",
]
