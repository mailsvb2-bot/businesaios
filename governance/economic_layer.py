from __future__ import annotations

"""Economic Autonomy Layer (Governance-time).

This layer is *not* DecisionCore and *not* Runtime.
It is a constitutional governance layer between DecisionCore and execution.

Responsibilities:
- Capital constraints (budget gating)
- Strategic horizon (myopic veto)
- Survival protection (system survival invariant)
- Economic governance review (liquidity / runway / ROI / spend caps)

NO side-effects. Deterministic.
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Mapping

from core.economics.capital_engine import (
    CapitalAllocationEngine,
    CapitalState,
    WorldState as CapitalWorldState,
)
from survival.controller import SurvivalController, SurvivalVerdict
from core.strategic_horizon.engine import (
    EconomyState,
    ExternalContext,
    LearningState,
    ProductState,
    RiskState,
    StrategicHorizonEngine,
    SystemState as HorizonSystemState,
    StrategicVector,
    UserDynamics,
)
from governance.economic_layer_env import is_strict_mode
from governance.economic_layer_world import load_world_or_degraded
from governance.economic import EconomicPolicyConfig, EconomicPolicyEngine, EconomicPolicyVerdict


@dataclass(frozen=True)
class EconomicLayerVerdict:
    allow: bool
    reason: Optional[str] = None
    allocation: Optional[Any] = None
    strategic: Optional[StrategicVector] = None
    survival: Optional[SurvivalVerdict] = None
    operator_required: bool = False
    economic: Optional[EconomicPolicyVerdict] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class EconomicAutonomyLayer:
    """Canonical governance-time autonomy layer orchestrator.

    This remains a thin orchestrator and must not become a second brain.
    Decision choice still belongs to DecisionCore. This layer only vetoes or
    escalates already-proposed actions using deterministic governance rules.
    """

    def __init__(
        self,
        capital_engine: CapitalAllocationEngine | None = None,
        horizon_engine: StrategicHorizonEngine | None = None,
        survival: SurvivalController | None = None,
        economic_policy_engine: EconomicPolicyEngine | None = None,
        economic_policy_config: EconomicPolicyConfig | None = None,
    ) -> None:
        self.capital_engine = capital_engine or CapitalAllocationEngine()
        self.horizon_engine = horizon_engine or StrategicHorizonEngine()
        self._economic_policy_config = economic_policy_config or EconomicPolicyConfig()
        self._economic_policy_engine = economic_policy_engine or EconomicPolicyEngine(config=self._economic_policy_config)
        if survival is not None:
            self.survival = survival
        else:
            class _AlwaysAliveMetrics:
                def get_metrics(self):
                    from survival.controller import SurvivalMetrics
                    return SurvivalMetrics(
                        cashflow=1.0,
                        churn_rate=0.0,
                        error_rate=0.0,
                        runtime_alive=True,
                        policy_health=1.0,
                    )
            self.survival = SurvivalController(_AlwaysAliveMetrics())

    def review(self, *args: Any, **kwargs: Any) -> EconomicLayerVerdict:
        strict = is_strict_mode()
        if args and len(args) >= 2:
            decision = args[0]
            world_state = args[1]
        else:
            decision = kwargs.get("decision", kwargs.get("decision_env", None))
            world_state = kwargs.get("world_state", None)

        decision_env = decision

        survival_verdict = self.survival.evaluate()
        if not survival_verdict.allow_execution:
            return EconomicLayerVerdict(
                allow=False,
                reason=f"survival_block:{survival_verdict.reason}",
                survival=survival_verdict,
            )

        if isinstance(world_state, dict) and world_state.get("mode") == "degraded":
            action = None
            try:
                action = getattr(decision_env.decision, "action", None)
            except (AttributeError, TypeError):
                try:
                    action = getattr(decision_env, "action", None)
                except (AttributeError, TypeError):
                    action = None
            if str(action) != "noop@v1":
                return EconomicLayerVerdict(False, f"degraded_world:{world_state.get('reason', 'missing')}", survival=survival_verdict)

        capital_state = self._coerce_capital_state(self._read_field(world_state, "capital", None))
        horizon_state = self._coerce_horizon_state(world_state, self._read_field(world_state, "horizon_state", None))

        if strict:
            if capital_state is None:
                return EconomicLayerVerdict(False, "missing_capital_state", survival=survival_verdict)
            if horizon_state is None:
                return EconomicLayerVerdict(False, "missing_horizon_state", survival=survival_verdict)

        allocation = None
        if capital_state is not None:
            decision_cost = self._coerce_float(self._read_field(decision, "cost", self._read_field(decision_env, "cost", 0.0)), 0.0)
            try:
                if hasattr(self.capital_engine, "allow_spend") and not self.capital_engine.allow_spend(decision_cost, capital_state):
                    return EconomicLayerVerdict(False, "capital_limit", survival=survival_verdict)
                if all(self._read_field(world_state, a, None) is not None for a in ("ltv", "cac", "growth_rate", "churn_rate", "uncertainty")):
                    cw = CapitalWorldState(
                        capital=capital_state,
                        ltv=float(self._read_field(world_state, "ltv", 0.0)),
                        cac=float(self._read_field(world_state, "cac", 0.0)),
                        growth_rate=float(self._read_field(world_state, "growth_rate", 0.0)),
                        churn_rate=float(self._read_field(world_state, "churn_rate", 0.0)),
                        uncertainty=float(self._read_field(world_state, "uncertainty", 0.0)),
                    )
                    allocation = self.capital_engine.allocate(cw)
            except (TypeError, ValueError, KeyError) as data_err:
                import logging
                logging.getLogger(__name__).warning("capital_engine data error: %s", data_err)
                if strict:
                    return EconomicLayerVerdict(False, "capital_engine_data_error", survival=survival_verdict)
            except Exception as engine_err:
                import logging
                logging.getLogger(__name__).exception("capital_engine failed: %s", engine_err)
                if strict:
                    return EconomicLayerVerdict(False, "capital_engine_error", survival=survival_verdict)
        elif strict:
            return EconomicLayerVerdict(False, "capital_state_missing", survival=survival_verdict)

        strategic = None
        if horizon_state is not None:
            try:
                if isinstance(horizon_state, HorizonSystemState):
                    strategic = self.horizon_engine.evaluate(horizon_state)
                else:
                    strategic = self.horizon_engine.evaluate(horizon_state)
                if hasattr(self.horizon_engine, "veto_if_myopic") and self.horizon_engine.veto_if_myopic(strategic, decision_env):
                    return EconomicLayerVerdict(False, "myopic_decision", allocation=allocation, strategic=strategic, survival=survival_verdict)
            except (TypeError, ValueError, KeyError) as data_err:
                import logging
                logging.getLogger(__name__).warning("horizon_engine data error: %s", data_err)
                if strict:
                    return EconomicLayerVerdict(False, "horizon_engine_data_error", allocation=allocation, survival=survival_verdict)
            except Exception as horizon_err:
                import logging
                logging.getLogger(__name__).exception("horizon_engine failed: %s", horizon_err)
                if strict:
                    return EconomicLayerVerdict(False, "horizon_engine_error", allocation=allocation, survival=survival_verdict)
        elif strict:
            return EconomicLayerVerdict(False, "horizon_state_missing", allocation=allocation, survival=survival_verdict)

        economic_verdict = self._economic_policy_engine.review(decision_env, world_state)
        if not economic_verdict.allowed or economic_verdict.operator_required:
            reason = economic_verdict.reason
            if economic_verdict.operator_required and not reason.startswith("economic_review:"):
                reason = f"economic_review:{reason}"
            return EconomicLayerVerdict(
                allow=False,
                reason=reason,
                allocation=allocation,
                strategic=strategic,
                survival=survival_verdict,
                operator_required=economic_verdict.operator_required,
                economic=economic_verdict,
                metadata=dict(economic_verdict.metadata),
            )

        return EconomicLayerVerdict(
            True,
            allocation=allocation,
            strategic=strategic,
            survival=survival_verdict,
            operator_required=False,
            economic=economic_verdict,
            metadata=dict(economic_verdict.metadata),
        )


    @classmethod
    def _coerce_capital_state(cls, source: Any) -> CapitalState | None:
        if source is None:
            return None
        if isinstance(source, CapitalState):
            return source
        if isinstance(source, Mapping):
            cash_balance = cls._coerce_float(source.get("cash_balance", source.get("cash", source.get("balance", 0.0))), 0.0)
            marketing_budget = cls._coerce_float(source.get("marketing_budget", source.get("budget", cash_balance)), cash_balance)
            compute_budget = cls._coerce_float(source.get("compute_budget", 0.0), 0.0)
            risk_limits = cls._coerce_float(source.get("risk_limits", source.get("risk_limit", 0.0)), 0.0)
            runway_days = cls._coerce_float(source.get("runway_days", source.get("cash_runway_days", 30.0)), 30.0)
            reserve = cls._coerce_float(source.get("reserve", cash_balance * 0.2), cash_balance * 0.2)
            return CapitalState(
                cash_balance=cash_balance,
                marketing_budget=max(0.0, marketing_budget),
                compute_budget=max(0.0, compute_budget),
                risk_limits=max(0.0, risk_limits),
                runway_days=max(0.0, runway_days),
                reserve=max(0.0, reserve),
            )
        if all(hasattr(source, field) for field in ("cash_balance", "marketing_budget", "compute_budget", "risk_limits", "runway_days", "reserve")):
            return CapitalState(
                cash_balance=cls._coerce_float(getattr(source, "cash_balance", 0.0)),
                marketing_budget=cls._coerce_float(getattr(source, "marketing_budget", 0.0)),
                compute_budget=cls._coerce_float(getattr(source, "compute_budget", 0.0)),
                risk_limits=cls._coerce_float(getattr(source, "risk_limits", 0.0)),
                runway_days=cls._coerce_float(getattr(source, "runway_days", 30.0), 30.0),
                reserve=cls._coerce_float(getattr(source, "reserve", 0.0)),
            )
        numeric = cls._coerce_float(source, 0.0)
        if numeric <= 0.0:
            return None
        return CapitalState(
            cash_balance=numeric,
            marketing_budget=numeric,
            compute_budget=0.0,
            risk_limits=0.0,
            runway_days=30.0,
            reserve=numeric * 0.2,
        )

    @classmethod
    def _coerce_horizon_state(cls, world_state: Any, source: Any) -> HorizonSystemState | None:
        if isinstance(source, HorizonSystemState):
            return source
        data = source if isinstance(source, Mapping) else {}
        world = world_state if isinstance(world_state, Mapping) else {}
        economy_data = data.get("economy") if isinstance(data, Mapping) else None
        users_data = data.get("users") if isinstance(data, Mapping) else None
        learning_data = data.get("learning") if isinstance(data, Mapping) else None
        risk_data = data.get("risk") if isinstance(data, Mapping) else None
        product_data = data.get("product") if isinstance(data, Mapping) else None
        external_data = data.get("external") if isinstance(data, Mapping) else None
        return HorizonSystemState(
            ts=cls._coerce_float((data.get("ts") if isinstance(data, Mapping) else None) or world.get("ts", 0.0), 0.0),
            economy=EconomyState(
                ltv_mean=cls._coerce_float((economy_data or {}).get("ltv_mean", world.get("ltv", 0.0)), 0.0),
                cac_mean=cls._coerce_float((economy_data or {}).get("cac_mean", world.get("cac", 0.0)), 0.0),
                margin=cls._coerce_float((economy_data or {}).get("margin", world.get("margin", 0.0)), 0.0),
                cash_runway_days=cls._coerce_float((economy_data or {}).get("cash_runway_days", world.get("runway_days", 30.0)), 30.0),
            ),
            users=UserDynamics(
                retention_d1=cls._coerce_float((users_data or {}).get("retention_d1", world.get("retention_d1", 1.0)), 1.0),
                retention_d7=cls._coerce_float((users_data or {}).get("retention_d7", world.get("retention_d7", 1.0)), 1.0),
                retention_d30=cls._coerce_float((users_data or {}).get("retention_d30", world.get("retention_d30", 1.0)), 1.0),
            ),
            learning=LearningState(
                offline_score=cls._coerce_float((learning_data or {}).get("offline_score", 0.5), 0.5),
                online_reward_confidence=cls._coerce_float((learning_data or {}).get("online_reward_confidence", 0.5), 0.5),
                policy_divergence=cls._coerce_float((learning_data or {}).get("policy_divergence", 0.0), 0.0),
            ),
            risk=RiskState(
                financial_risk=cls._coerce_float((risk_data or {}).get("financial_risk", world.get("uncertainty", 0.0)), 0.0),
                ux_risk=cls._coerce_float((risk_data or {}).get("ux_risk", 0.0), 0.0),
                regulatory_risk=cls._coerce_float((risk_data or {}).get("regulatory_risk", 0.0), 0.0),
            ),
            product=ProductState(
                growth_rate=cls._coerce_float((product_data or {}).get("growth_rate", world.get("growth_rate", 0.0)), 0.0),
                churn_rate=cls._coerce_float((product_data or {}).get("churn_rate", world.get("churn_rate", 0.0)), 0.0),
            ),
            external=ExternalContext(
                seasonality=cls._coerce_float((external_data or {}).get("seasonality", 0.0), 0.0),
                market_pressure=cls._coerce_float((external_data or {}).get("market_pressure", 0.0), 0.0),
            ),
        )

    @staticmethod
    def _read_field(source: Any, name: str, default: Any = None) -> Any:
        if isinstance(source, Mapping):
            return source.get(name, default)
        return getattr(source, name, default)

    @staticmethod
    def _coerce_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)
