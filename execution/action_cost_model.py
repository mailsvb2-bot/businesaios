from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from execution.action_budget_engine import ActionBudgetDecision


CANON_ACTION_COST_MODEL = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    if parsed < 0.0:
        return 0.0
    return float(parsed)


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return max(0, int(parsed))


def _text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class CanonicalActionCost:
    estimated_cost: float = 0.0
    requested_budget: float = 0.0
    budget_delta: float = 0.0
    budget_change_amount: float = 0.0
    outbound_count: int = 0
    publication_count: int = 0
    irreversible_count: int = 0
    execution_risk_weight: float = 0.0
    channel: str = "default"
    currency: str = "RUB"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_cost": float(self.estimated_cost),
            "requested_budget": float(self.requested_budget),
            "budget_delta": float(self.budget_delta),
            "budget_change_amount": float(self.budget_change_amount),
            "outbound_count": int(self.outbound_count),
            "publication_count": int(self.publication_count),
            "irreversible_count": int(self.irreversible_count),
            "execution_risk_weight": float(self.execution_risk_weight),
            "channel": self.channel,
            "currency": self.currency,
            "metadata": dict(self.metadata),
        }


class ActionCostModel:
    """
    Canonical cost normalization layer.

    Important:
    - Not a decision module.
    - Not a second budget engine.
    - Prefers already computed ActionBudgetDecision when available.
    - Falls back to payload normalization only when a canonical budget decision
      is not available.
    """

    def from_sources(
        self,
        *,
        action_type: str,
        payload: Mapping[str, Any] | None,
        request: Any | None = None,
        budget_decision: ActionBudgetDecision | None = None,
    ) -> CanonicalActionCost:
        if budget_decision is not None:
            return self.from_budget_decision(
                action_type=action_type,
                payload=payload,
                request=request,
                budget_decision=budget_decision,
            )
        return self.from_action_payload(
            action_type=action_type,
            payload=payload,
            request=request,
        )

    def from_budget_decision(
        self,
        *,
        action_type: str,
        payload: Mapping[str, Any] | None,
        request: Any | None,
        budget_decision: ActionBudgetDecision,
    ) -> CanonicalActionCost:
        action_payload = _safe_dict(payload)
        economy = _safe_dict(action_payload.get("economy"))
        request_economy = _safe_dict(getattr(request, "economy", {}))
        constraints = _safe_dict(getattr(request, "constraints", {}))

        requested_budget = _safe_float(
            action_payload.get("requested_budget"),
            default=_safe_float(
                economy.get("requested_budget"),
                default=_safe_float(request_economy.get("requested_budget")),
            ),
        )
        budget_delta = _safe_float(
            economy.get("budget_delta"),
            default=_safe_float(action_payload.get("budget_delta")),
        )

        return CanonicalActionCost(
            estimated_cost=float(budget_decision.cost.estimated_cost),
            requested_budget=requested_budget,
            budget_delta=budget_delta,
            budget_change_amount=float(budget_decision.cost.budget_change_amount),
            outbound_count=int(budget_decision.cost.outbound_count),
            publication_count=int(budget_decision.cost.publication_count),
            irreversible_count=int(budget_decision.cost.irreversible_count),
            execution_risk_weight=max(
                0.0,
                _safe_float(
                    action_payload.get("execution_risk_weight"),
                    default=_safe_float(
                        constraints.get("execution_risk_weight"),
                        default=_safe_float(economy.get("execution_risk_weight")),
                    ),
                ),
            ),
            channel=(
                _text(action_payload.get("channel"))
                or _text(economy.get("channel"))
                or _text(request_economy.get("channel"))
                or "default"
            ),
            currency=(
                _text(action_payload.get("currency"))
                or _text(economy.get("currency"))
                or _text(request_economy.get("currency"))
                or _text(budget_decision.cost.currency)
                or _text(budget_decision.snapshot_after.currency)
                or "RUB"
            ),
            metadata={
                "owner": "execution.action_cost_model",
                "source": "budget_decision",
                "action_type": _text(action_type),
            },
        )

    def from_action_payload(
        self,
        *,
        action_type: str,
        payload: Mapping[str, Any] | None,
        request: Any | None = None,
    ) -> CanonicalActionCost:
        action_payload = _safe_dict(payload)
        economy = _safe_dict(action_payload.get("economy"))
        constraints = _safe_dict(getattr(request, "constraints", {}))
        request_economy = _safe_dict(getattr(request, "economy", {}))

        requested_budget = _safe_float(
            action_payload.get("requested_budget"),
            default=_safe_float(
                economy.get("requested_budget"),
                default=_safe_float(request_economy.get("requested_budget")),
            ),
        )
        budget_delta = _safe_float(
            economy.get("budget_delta"),
            default=_safe_float(action_payload.get("budget_delta")),
        )
        estimated_cost = _safe_float(
            action_payload.get("estimated_cost"),
            default=_safe_float(
                action_payload.get("cost"),
                default=_safe_float(action_payload.get("expected_cost")),
            ),
        )

        outbound_count = max(
            _safe_int(action_payload.get("outbound_count")),
            1 if any(token in _text(action_type).lower() for token in ("send", "email", "message", "notify", "outreach")) else 0,
        )
        publication_count = max(
            _safe_int(action_payload.get("publication_count")),
            1 if any(token in _text(action_type).lower() for token in ("publish", "post", "launch")) else 0,
        )
        irreversible_count = max(
            _safe_int(action_payload.get("irreversible_count")),
            1 if _safe_dict(action_payload.get("governance")).get("irreversible") else 0,
        )
        budget_change_amount = max(
            requested_budget,
            budget_delta,
            _safe_float(action_payload.get("budget_change_amount")),
        )

        return CanonicalActionCost(
            estimated_cost=estimated_cost,
            requested_budget=requested_budget,
            budget_delta=budget_delta,
            budget_change_amount=budget_change_amount,
            outbound_count=outbound_count,
            publication_count=publication_count,
            irreversible_count=irreversible_count,
            execution_risk_weight=max(
                0.0,
                _safe_float(
                    action_payload.get("execution_risk_weight"),
                    default=_safe_float(
                        constraints.get("execution_risk_weight"),
                        default=_safe_float(economy.get("execution_risk_weight")),
                    ),
                ),
            ),
            channel=(
                _text(action_payload.get("channel"))
                or _text(economy.get("channel"))
                or _text(request_economy.get("channel"))
                or "default"
            ),
            currency=(
                _text(action_payload.get("currency"))
                or _text(economy.get("currency"))
                or _text(request_economy.get("currency"))
                or "RUB"
            ),
            metadata={
                "owner": "execution.action_cost_model",
                "source": "payload_fallback",
                "action_type": _text(action_type),
            },
        )


__all__ = [
    "CANON_ACTION_COST_MODEL",
    "ActionCostModel",
    "CanonicalActionCost",
]
