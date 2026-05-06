from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from execution.action_capability_matrix import get_action_capability
from execution.adaptive_budget_policy import AdaptiveBudgetPolicy


CANON_ACTION_BUDGET_ENGINE = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object) -> str:
    return str(value or '').strip()


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


@dataclass(frozen=True)
class ActionBudgetCost:
    estimated_cost: float
    currency: str
    outbound_count: int
    publication_count: int
    irreversible_count: int
    budget_change_amount: float
    reasoning: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_cost": float(self.estimated_cost),
            "currency": str(self.currency),
            "outbound_count": int(self.outbound_count),
            "publication_count": int(self.publication_count),
            "irreversible_count": int(self.irreversible_count),
            "budget_change_amount": float(self.budget_change_amount),
            "reasoning": list(self.reasoning),
        }


@dataclass(frozen=True)
class ActionBudgetSnapshot:
    spent_total: float = 0.0
    spent_this_run: float = 0.0
    outbound_total: int = 0
    publications_total: int = 0
    irreversible_total: int = 0
    budget_change_total: float = 0.0
    step_count: int = 0
    currency: str = "USD"

    def to_dict(self) -> dict[str, Any]:
        return {
            "spent_total": float(self.spent_total),
            "spent_this_run": float(self.spent_this_run),
            "outbound_total": int(self.outbound_total),
            "publications_total": int(self.publications_total),
            "irreversible_total": int(self.irreversible_total),
            "budget_change_total": float(self.budget_change_total),
            "step_count": int(self.step_count),
            "currency": str(self.currency),
        }


@dataclass(frozen=True)
class ActionBudgetDecision:
    allowed: bool
    reason: str
    cost: ActionBudgetCost
    snapshot_before: ActionBudgetSnapshot
    snapshot_after: ActionBudgetSnapshot
    violated_limits: tuple[str, ...] = ()
    budget_posture: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": bool(self.allowed),
            "reason": str(self.reason),
            "cost": self.cost.to_dict(),
            "snapshot_before": self.snapshot_before.to_dict(),
            "snapshot_after": self.snapshot_after.to_dict(),
            "violated_limits": list(self.violated_limits),
            "budget_posture": dict(self.budget_posture or {}),
        }


class ActionBudgetEngine:
    def __init__(self, *, adaptive_budget_policy: AdaptiveBudgetPolicy | None = None) -> None:
        self._adaptive_budget_policy = adaptive_budget_policy or AdaptiveBudgetPolicy()

    def estimate_cost(self, *, action_type: str, payload: Mapping[str, Any] | None) -> ActionBudgetCost:
        action = _text(action_type)
        body = _safe_dict(payload)
        capability = get_action_capability(action)
        reasons: list[str] = []

        explicit_cost = _safe_float(body.get("estimated_cost") or body.get("cost") or body.get("expected_cost") or 0.0)
        currency = _text(body.get("currency") or body.get("budget_currency") or "USD") or "USD"
        outbound = max(0, _safe_int(body.get("outbound_count") or body.get("message_count") or body.get("email_count") or body.get("recipient_count") or 0))
        publication_count = max(0, _safe_int(body.get("publication_count") or body.get("new_pages") or body.get("new_listings") or body.get("new_assets") or 0))
        irreversible_count = 0 if capability.reversible else 1
        budget_change_amount = max(0.0, _safe_float(body.get("budget_change_amount") or body.get("proposed_budget_delta") or body.get("daily_budget_delta") or 0.0))

        if explicit_cost > 0.0:
            reasons.append("explicit_cost")
        else:
            baseline = 0.0
            if capability.action_class in {"ads_write", "budget_change"}:
                baseline += 2.5
                reasons.append("baseline_ads_write")
            elif capability.action_class in {"communications_write"}:
                baseline += 0.2
                reasons.append("baseline_communications_write")
            elif capability.action_class in {"seo_publish", "platform_listing_write", "profile_publish"}:
                baseline += 1.0
                reasons.append("baseline_publication_write")
            elif capability.action_class in {"marketplace_routing"}:
                baseline += 0.5
                reasons.append("baseline_marketplace_routing")
            else:
                baseline += 0.1
                reasons.append("baseline_internal")
            baseline += float(outbound) * 0.05
            baseline += float(publication_count) * 0.75
            baseline += float(budget_change_amount) * 0.02
            explicit_cost = baseline

        return ActionBudgetCost(float(max(0.0, explicit_cost)), currency, int(outbound), int(publication_count), int(irreversible_count), float(budget_change_amount), tuple(reasons))

    def snapshot_from_feedback(self, *, request: Any, previous_feedback: Mapping[str, Any] | None) -> ActionBudgetSnapshot:
        feedback = _safe_dict(previous_feedback)
        budget_state = _safe_dict(feedback.get("action_budget_state"))
        economy = _safe_dict(getattr(request, "economy", {}))
        currency = _text(budget_state.get("currency") or economy.get("currency") or economy.get("budget_currency") or "USD") or "USD"
        return ActionBudgetSnapshot(
            spent_total=_safe_float(budget_state.get("spent_total")),
            spent_this_run=_safe_float(budget_state.get("spent_this_run")),
            outbound_total=max(0, _safe_int(budget_state.get("outbound_total"))),
            publications_total=max(0, _safe_int(budget_state.get("publications_total"))),
            irreversible_total=max(0, _safe_int(budget_state.get("irreversible_total"))),
            budget_change_total=max(0.0, _safe_float(budget_state.get("budget_change_total"))),
            step_count=max(0, _safe_int(budget_state.get("step_count"))),
            currency=currency,
        )

    def evaluate(self, *, request: Any, action_type: str, payload: Mapping[str, Any] | None, previous_feedback: Mapping[str, Any] | None) -> ActionBudgetDecision:
        snapshot = self.snapshot_from_feedback(request=request, previous_feedback=previous_feedback)
        economy = _safe_dict(getattr(request, "economy", {}))
        constraints = _safe_dict(getattr(request, "constraints", {}))
        performance = _safe_dict(_safe_dict(getattr(request, "meta", {})).get("performance_learning"))
        cost = self.estimate_cost(action_type=action_type, payload=payload)

        limits = {
            'max_run_cost': _safe_float(economy.get("max_run_cost") or economy.get("run_budget") or constraints.get("max_run_cost") or 0.0),
            'max_total_cost': _safe_float(economy.get("max_total_cost") or economy.get("total_budget") or constraints.get("max_total_cost") or 0.0),
            'max_outbound_total': max(0, _safe_int(economy.get("max_outbound_total") or constraints.get("max_outbound_total") or 0)),
            'max_publications_total': max(0, _safe_int(economy.get("max_publications_total") or constraints.get("max_publications_total") or 0)),
            'max_irreversible_total': max(0, _safe_int(economy.get("max_irreversible_total") or constraints.get("max_irreversible_total") or 0)),
            'max_budget_change_total': _safe_float(economy.get("max_budget_change_total") or constraints.get("max_budget_change_total") or 0.0),
        }
        adapted_limits = self._adaptive_budget_policy.apply(posture_payload=performance.get('budget_posture_detail') or performance, limits=limits)

        after = ActionBudgetSnapshot(
            spent_total=float(snapshot.spent_total + cost.estimated_cost),
            spent_this_run=float(snapshot.spent_this_run + cost.estimated_cost),
            outbound_total=int(snapshot.outbound_total + cost.outbound_count),
            publications_total=int(snapshot.publications_total + cost.publication_count),
            irreversible_total=int(snapshot.irreversible_total + cost.irreversible_count),
            budget_change_total=float(snapshot.budget_change_total + cost.budget_change_amount),
            step_count=int(snapshot.step_count + 1),
            currency=str(snapshot.currency or cost.currency or "USD"),
        )

        violations: list[str] = []
        if adapted_limits['max_run_cost'] > 0.0 and after.spent_this_run > adapted_limits['max_run_cost']:
            violations.append("max_run_cost")
        if adapted_limits['max_total_cost'] > 0.0 and after.spent_total > adapted_limits['max_total_cost']:
            violations.append("max_total_cost")
        if adapted_limits['max_outbound_total'] > 0 and after.outbound_total > adapted_limits['max_outbound_total']:
            violations.append("max_outbound_total")
        if adapted_limits['max_publications_total'] > 0 and after.publications_total > adapted_limits['max_publications_total']:
            violations.append("max_publications_total")
        if adapted_limits['max_irreversible_total'] > 0 and after.irreversible_total > adapted_limits['max_irreversible_total']:
            violations.append("max_irreversible_total")
        if adapted_limits['max_budget_change_total'] > 0.0 and after.budget_change_total > adapted_limits['max_budget_change_total']:
            violations.append("max_budget_change_total")

        return ActionBudgetDecision(
            allowed=not violations,
            reason="within_action_budget" if not violations else "action_budget_exceeded",
            cost=cost,
            snapshot_before=snapshot,
            snapshot_after=after,
            violated_limits=tuple(violations),
            budget_posture=_safe_dict(adapted_limits.get('budget_posture')),
        )


__all__ = ["CANON_ACTION_BUDGET_ENGINE", "ActionBudgetCost", "ActionBudgetDecision", "ActionBudgetEngine", "ActionBudgetSnapshot"]
