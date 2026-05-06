from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


CANON_OPERATIONAL_BUDGET = True

_OPERATIONAL_PREFIX = "operational_budget_"


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


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _prefixed(payload: Mapping[str, Any], name: str, default: Any = None) -> Any:
    if name in payload:
        return payload.get(name)
    prefixed_name = f"{_OPERATIONAL_PREFIX}{name}"
    if prefixed_name in payload:
        return payload.get(prefixed_name)
    return default


@dataclass(frozen=True, slots=True)
class BudgetWindowUsage:
    actions: int = 0
    outbound: int = 0
    new_assets: int = 0
    irreversible_actions: int = 0
    budget_change_amount: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "actions": int(self.actions),
            "outbound": int(self.outbound),
            "new_assets": int(self.new_assets),
            "irreversible_actions": int(self.irreversible_actions),
            "budget_change_amount": float(self.budget_change_amount),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "BudgetWindowUsage":
        payload = _safe_dict(value)
        return cls(
            actions=max(0, _safe_int(payload.get("actions"), default=0)),
            outbound=max(0, _safe_int(payload.get("outbound"), default=0)),
            new_assets=max(0, _safe_int(payload.get("new_assets"), default=0)),
            irreversible_actions=max(0, _safe_int(payload.get("irreversible_actions"), default=0)),
            budget_change_amount=max(0.0, _safe_float(payload.get("budget_change_amount"), default=0.0)),
        )


@dataclass(frozen=True, slots=True)
class OperationalBudget:
    max_actions_per_hour: int = 25
    max_actions_per_day: int = 100
    max_outbound_per_window: int = 20
    max_new_assets_per_day: int = 10
    max_irreversible_actions_per_window: int = 2
    max_budget_change_per_window: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_actions_per_hour": int(self.max_actions_per_hour),
            "max_actions_per_day": int(self.max_actions_per_day),
            "max_outbound_per_window": int(self.max_outbound_per_window),
            "max_new_assets_per_day": int(self.max_new_assets_per_day),
            "max_irreversible_actions_per_window": int(self.max_irreversible_actions_per_window),
            "max_budget_change_per_window": self.max_budget_change_per_window,
        }

    @classmethod
    def from_constraints(cls, constraints: Mapping[str, Any] | None) -> "OperationalBudget":
        payload = _safe_dict(constraints)
        raw_budget_change = _prefixed(payload, "max_budget_change_per_window")
        normalized = _text(raw_budget_change).casefold()
        max_budget_change = None if normalized in {"", "none", "unlimited"} or raw_budget_change is None else max(0.0, _safe_float(raw_budget_change))
        return cls(
            max_actions_per_hour=max(1, _safe_int(_prefixed(payload, "max_actions_per_hour", 25), default=25)),
            max_actions_per_day=max(1, _safe_int(_prefixed(payload, "max_actions_per_day", 100), default=100)),
            max_outbound_per_window=max(0, _safe_int(_prefixed(payload, "max_outbound_per_window", 20), default=20)),
            max_new_assets_per_day=max(0, _safe_int(_prefixed(payload, "max_new_assets_per_day", 10), default=10)),
            max_irreversible_actions_per_window=max(0, _safe_int(_prefixed(payload, "max_irreversible_actions_per_window", 2), default=2)),
            max_budget_change_per_window=max_budget_change,
        )


@dataclass(frozen=True, slots=True)
class OperationalBudgetDecision:
    allowed: bool
    reason: str
    violated_rules: tuple[str, ...] = ()
    budget: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    proposed_action_cost: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "violated_rules": list(self.violated_rules),
            "budget": dict(self.budget),
            "usage": dict(self.usage),
            "proposed_action_cost": dict(self.proposed_action_cost),
            "metadata": dict(self.metadata),
        }


class OperationalBudgetGuard:
    """
    Read-only helper for headless constraints.

    It does not replace BlastRadiusGuard and is intentionally not wired as a second
    execution gate. Runtime enforcement stays in the canonical blast-radius path.
    """

    def evaluate(
        self,
        *,
        budget: OperationalBudget,
        hour_usage: BudgetWindowUsage,
        day_usage: BudgetWindowUsage,
        proposed_action_cost: Mapping[str, Any] | None = None,
    ) -> OperationalBudgetDecision:
        cost = _safe_dict(proposed_action_cost)
        add_actions = max(1, _safe_int(cost.get("actions"), default=1))
        add_outbound = max(0, _safe_int(cost.get("outbound")))
        add_assets = max(0, _safe_int(cost.get("new_assets")))
        add_irreversible = max(0, _safe_int(cost.get("irreversible_actions")))
        add_budget_delta = max(0.0, _safe_float(cost.get("budget_change_amount")))
        violations: list[str] = []
        if hour_usage.actions + add_actions > budget.max_actions_per_hour:
            violations.append("max_actions_per_hour")
        if day_usage.actions + add_actions > budget.max_actions_per_day:
            violations.append("max_actions_per_day")
        if hour_usage.outbound + add_outbound > budget.max_outbound_per_window:
            violations.append("max_outbound_per_window")
        if day_usage.new_assets + add_assets > budget.max_new_assets_per_day:
            violations.append("max_new_assets_per_day")
        if hour_usage.irreversible_actions + add_irreversible > budget.max_irreversible_actions_per_window:
            violations.append("max_irreversible_actions_per_window")
        if budget.max_budget_change_per_window is not None and hour_usage.budget_change_amount + add_budget_delta > budget.max_budget_change_per_window:
            violations.append("max_budget_change_per_window")
        return OperationalBudgetDecision(
            allowed=not violations,
            reason="within_operational_budget" if not violations else "operational_budget_exceeded",
            violated_rules=tuple(violations),
            budget=budget.to_dict(),
            usage={"hour": hour_usage.to_dict(), "day": day_usage.to_dict()},
            proposed_action_cost={
                "actions": add_actions,
                "outbound": add_outbound,
                "new_assets": add_assets,
                "irreversible_actions": add_irreversible,
                "budget_change_amount": add_budget_delta,
            },
            metadata={
                "owner": "execution.operational_budget",
                "constraints_prefix_supported": True,
            },
        )


__all__ = [
    "CANON_OPERATIONAL_BUDGET",
    "BudgetWindowUsage",
    "OperationalBudget",
    "OperationalBudgetDecision",
    "OperationalBudgetGuard",
]
