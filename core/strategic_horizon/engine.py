from __future__ import annotations

from dataclasses import dataclass

from core.strategic_horizon.contracts import LearningRegime, StrategicMode
from core.strategic_horizon.cooldown import CooldownState
from core.strategic_horizon.mode_inference import can_expand, can_optimize, infer_mode, is_defense, is_unstable
from core.strategic_horizon.vector_math import compute_risk_budget, growth_pressure, learning_regime, select_horizon

CANONICAL_DECISION_OPTIMIZE_METHOD = "optimize"




@dataclass(frozen=True)
class EconomyState:
    ltv_mean: float
    cac_mean: float
    margin: float
    cash_runway_days: float


@dataclass(frozen=True)
class UserDynamics:
    retention_d1: float
    retention_d7: float
    retention_d30: float


@dataclass(frozen=True)
class LearningState:
    offline_score: float
    online_reward_confidence: float
    policy_divergence: float


@dataclass(frozen=True)
class RiskState:
    financial_risk: float
    ux_risk: float
    regulatory_risk: float


@dataclass(frozen=True)
class ProductState:
    growth_rate: float
    churn_rate: float


@dataclass(frozen=True)
class ExternalContext:
    seasonality: float
    market_pressure: float


@dataclass(frozen=True)
class SystemState:
    ts: float
    economy: EconomyState
    users: UserDynamics
    learning: LearningState
    risk: RiskState
    product: ProductState
    external: ExternalContext


@dataclass(frozen=True)
class StrategicVector:
    mode: StrategicMode
    horizon_days: int
    risk_budget: float
    growth_pressure: float
    learning_regime: LearningRegime
    evaluated_at: float


class StrategicHorizonEngine:
    """Canonical advisory engine; does not issue actions directly."""

    def __init__(self) -> None:
        self._cooldown = CooldownState()

    def evaluate(self, state: SystemState) -> StrategicVector:
        proposed_mode = self._infer_mode(state)
        mode = self._apply_cooldown(proposed_mode, state.ts)
        return StrategicVector(
            mode=mode,
            horizon_days=self._select_horizon(mode),
            risk_budget=self._compute_risk_budget(state, mode),
            growth_pressure=self._growth_pressure(state, mode),
            learning_regime=self._learning_regime(state, mode),
            evaluated_at=state.ts,
        )

    def _infer_mode(self, s: SystemState) -> StrategicMode:
        return infer_mode(s)

    def _is_defense(self, s: SystemState) -> bool:
        return is_defense(s)

    def _is_unstable(self, s: SystemState) -> bool:
        return is_unstable(s)

    def _can_expand(self, s: SystemState) -> bool:
        return can_expand(s)

    def _can_optimize(self, s: SystemState) -> bool:
        return can_optimize(s)

    def _apply_cooldown(self, proposed: StrategicMode, ts: float) -> StrategicMode:
        return self._cooldown.apply(proposed, ts)

    def _commit_mode(self, mode: StrategicMode, ts: float) -> None:
        self._cooldown.commit(mode, ts)

    def _select_horizon(self, mode: StrategicMode) -> int:
        return select_horizon(mode)

    def _compute_risk_budget(self, s: SystemState, mode: StrategicMode) -> float:
        return compute_risk_budget(s, mode)

    def _growth_pressure(self, s: SystemState, mode: StrategicMode) -> float:
        return growth_pressure(s, mode)

    def _learning_regime(self, s: SystemState, mode: StrategicMode) -> LearningRegime:
        return learning_regime(s, mode)


def veto_if_myopic(vector: StrategicVector, decision: object | None = None) -> bool:
    action = getattr(decision, "action", None) if decision is not None else None
    safe_actions = {"noop", "hold", "keep"}
    if vector.mode == StrategicMode.DEFENSE:
        if action is None:
            return False
        return str(action).lower() not in safe_actions
    if vector.mode == StrategicMode.STABILIZE:
        if action is None:
            return False
        return str(action).lower() in {"expand", "increase_spend", "deploy_policy"}
    return False
