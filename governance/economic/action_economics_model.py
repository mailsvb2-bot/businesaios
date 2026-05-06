from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from governance.economic.economic_policy_contract import EconomicPolicyConfig

CANON_NON_DECISION_MODULE = True


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    if math.isnan(result) or math.isinf(result):
        return float(default)
    return result


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", ""}:
            return False
    return bool(value)


def _to_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _read_field(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _read_payload(source: Any) -> Mapping[str, Any]:
    return _to_mapping(_read_field(source, "payload", {}))


def _normalize_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        normalized = value.strip()
        return (normalized,) if normalized else ()
    if isinstance(value, Iterable):
        result: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized:
                result.append(normalized)
        return tuple(result)
    normalized = str(value).strip()
    return (normalized,) if normalized else ()


def _normalize_float_map(value: Any) -> dict[str, float]:
    mapping = _to_mapping(value)
    result: dict[str, float] = {}
    for key, raw in mapping.items():
        result[str(key)] = _safe_float(raw, 0.0)
    return result


def _pick_requested_budget(requested_budget: float, budget_delta: float) -> float:
    return max(0.0, requested_budget, budget_delta)


@dataclass(frozen=True)
class ActionEconomicsSnapshot:
    currency: str = "RUB"
    cash_on_hand: float = 0.0
    protected_cash_reserve: float = 0.0
    available_liquidity: float = 0.0
    receivables_due_30d: float = 0.0
    payables_due_30d: float = 0.0
    monthly_burn: float = 0.0
    gross_margin: float = 0.0
    target_margin: float = 0.0
    current_spend: float = 0.0
    planned_spend: float = 0.0
    hard_spend_cap: float = 0.0
    expected_incremental_revenue: float = 0.0
    expected_incremental_gross_profit: float = 0.0
    expected_incremental_roi: float = 0.0
    drawdown_ratio: float = 0.0
    required_liquidity_buffer: float = 0.0
    open_stop_loss_flags: tuple[str, ...] = ()
    portfolio_budgets: Mapping[str, float] = field(default_factory=dict)
    portfolio_weights: Mapping[str, float] = field(default_factory=dict)
    channel_risk_scores: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def total_liquidity(self) -> float:
        return max(0.0, self.available_liquidity + self.receivables_due_30d - self.payables_due_30d)

    @classmethod
    def from_sources(
        cls,
        *,
        decision: Any = None,
        world_state: Any = None,
        config: EconomicPolicyConfig | None = None,
    ) -> "ActionEconomicsSnapshot":
        policy_config = config or EconomicPolicyConfig()
        raw_decision = _read_field(decision, "decision", decision)
        payload = _read_payload(raw_decision)
        decision_economy = _to_mapping(payload.get("economy"))

        if isinstance(world_state, Mapping):
            state_economy = _to_mapping(world_state.get("economics_state") or world_state.get("economy") or {})
        else:
            state_economy = _to_mapping(_read_field(world_state, "economics_state", None) or _read_field(world_state, "economy", {}))

        merged = {**state_economy, **decision_economy}
        cash_on_hand = _safe_float(merged.get("cash_on_hand"), 0.0)
        available_liquidity = _safe_float(merged.get("available_liquidity"), cash_on_hand)

        return cls(
            currency=str(merged.get("currency") or policy_config.currency),
            cash_on_hand=cash_on_hand,
            protected_cash_reserve=_safe_float(merged.get("protected_cash_reserve")),
            available_liquidity=available_liquidity,
            receivables_due_30d=_safe_float(merged.get("receivables_due_30d")),
            payables_due_30d=_safe_float(merged.get("payables_due_30d")),
            monthly_burn=_safe_float(merged.get("monthly_burn")),
            gross_margin=_safe_float(merged.get("gross_margin")),
            target_margin=_safe_float(merged.get("target_margin")),
            current_spend=_safe_float(merged.get("current_spend")),
            planned_spend=_safe_float(merged.get("planned_spend")),
            hard_spend_cap=_safe_float(merged.get("hard_spend_cap")),
            expected_incremental_revenue=_safe_float(merged.get("expected_incremental_revenue")),
            expected_incremental_gross_profit=_safe_float(merged.get("expected_incremental_gross_profit")),
            expected_incremental_roi=_safe_float(merged.get("expected_incremental_roi")),
            drawdown_ratio=max(0.0, min(1.0, _safe_float(merged.get("drawdown_ratio"), 0.0))),
            required_liquidity_buffer=max(0.0, _safe_float(merged.get("required_liquidity_buffer"), cash_on_hand * policy_config.required_liquidity_buffer_ratio)),
            open_stop_loss_flags=_normalize_str_tuple(merged.get("open_stop_loss_flags")),
            portfolio_budgets=_normalize_float_map(merged.get("portfolio_budgets")),
            portfolio_weights=_normalize_float_map(merged.get("portfolio_weights")),
            channel_risk_scores=_normalize_float_map(merged.get("channel_risk_scores")),
            metadata=_to_mapping(merged.get("metadata")),
        )


@dataclass(frozen=True)
class ActionEconomicsIntent:
    action_type: str
    channel: str = "default"
    requested_budget: float = 0.0
    budget_delta: float = 0.0
    expected_incremental_revenue: float = 0.0
    expected_incremental_gross_profit: float = 0.0
    expected_incremental_roi: float = 0.0
    min_expected_roi: float = 0.0
    priority: int = 50
    horizon_days: int = 30
    can_pause: bool = True
    required_liquidity_buffer: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_decision(cls, decision: Any, *, config: EconomicPolicyConfig | None = None) -> "ActionEconomicsIntent":
        policy_config = config or EconomicPolicyConfig()
        raw_decision = _read_field(decision, "decision", decision)
        payload = _read_payload(raw_decision)
        economy = _to_mapping(payload.get("economy"))
        action_type = str(_read_field(raw_decision, "action", payload.get("action_type") or "unknown"))
        return cls(
            action_type=action_type,
            channel=str(payload.get("channel") or economy.get("channel") or "default"),
            requested_budget=_safe_float(economy.get("requested_budget", payload.get("requested_budget"))),
            budget_delta=_safe_float(economy.get("budget_delta", payload.get("budget_delta"))),
            expected_incremental_revenue=_safe_float(economy.get("expected_incremental_revenue")),
            expected_incremental_gross_profit=_safe_float(economy.get("expected_incremental_gross_profit")),
            expected_incremental_roi=_safe_float(economy.get("expected_incremental_roi")),
            min_expected_roi=_safe_float(economy.get("min_expected_roi"), policy_config.default_min_expected_roi),
            priority=max(0, _safe_int(economy.get("priority", payload.get("priority", 50)), 50)),
            horizon_days=max(1, _safe_int(economy.get("horizon_days", payload.get("horizon_days", 30)), 30)),
            can_pause=_safe_bool(economy.get("can_pause", True), True),
            required_liquidity_buffer=max(0.0, _safe_float(economy.get("required_liquidity_buffer"), 0.0)),
            metadata=_to_mapping(economy.get("metadata")),
        )


@dataclass(frozen=True)
class ActionEconomicsAssessment:
    requested_budget: float
    total_encumbrance: float
    cash_after_action: float
    liquidity_after_action: float
    reserve_gap: float
    runway_days_after_action: float
    expected_roi: float
    expected_margin_after_action: float


@dataclass(frozen=True)
class EconomicPolicyVerdict:
    allowed: bool
    operator_required: bool
    reason: str
    reasons: tuple[str, ...] = ()
    checks: tuple[Any, ...] = ()
    survival_mode: str = "normal"
    assessment: ActionEconomicsAssessment | None = None
    portfolio_allocation: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


def build_assessment(intent: ActionEconomicsIntent, snapshot: ActionEconomicsSnapshot) -> ActionEconomicsAssessment:
    requested_budget = _pick_requested_budget(intent.requested_budget, intent.budget_delta)
    liquidity_buffer = max(0.0, intent.required_liquidity_buffer or snapshot.required_liquidity_buffer)
    total_encumbrance = max(0.0, requested_budget + liquidity_buffer)
    cash_after_action = max(0.0, snapshot.cash_on_hand - total_encumbrance)
    liquidity_after_action = max(0.0, snapshot.total_liquidity - total_encumbrance)
    reserve_gap = max(0.0, snapshot.protected_cash_reserve - cash_after_action)
    monthly_burn = max(0.0, snapshot.monthly_burn)
    if monthly_burn <= 0.0:
        runway_days_after_action = 3650.0
    else:
        free_cash_after_action = max(0.0, cash_after_action - snapshot.protected_cash_reserve)
        runway_days_after_action = (free_cash_after_action / monthly_burn) * 30.0
    expected_profit = intent.expected_incremental_gross_profit if intent.expected_incremental_gross_profit != 0.0 else snapshot.expected_incremental_gross_profit
    expected_revenue = intent.expected_incremental_revenue if intent.expected_incremental_revenue != 0.0 else snapshot.expected_incremental_revenue
    if intent.expected_incremental_roi != 0.0:
        expected_roi = intent.expected_incremental_roi
    elif requested_budget > 0.0:
        expected_roi = expected_profit / requested_budget
    else:
        expected_roi = snapshot.expected_incremental_roi
    if expected_revenue > 0.0:
        expected_margin_after_action = expected_profit / expected_revenue
    else:
        expected_margin_after_action = snapshot.gross_margin
    return ActionEconomicsAssessment(
        requested_budget=requested_budget,
        total_encumbrance=total_encumbrance,
        cash_after_action=cash_after_action,
        liquidity_after_action=liquidity_after_action,
        reserve_gap=reserve_gap,
        runway_days_after_action=runway_days_after_action,
        expected_roi=expected_roi,
        expected_margin_after_action=expected_margin_after_action,
    )
