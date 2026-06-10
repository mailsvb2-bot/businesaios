from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Sequence

from config.system_config import OptimizationObjective
from core.math.advanced_models import DemandSource, LinearThompsonBandit, demand_potential, optimal_price_from_grid
from growth.budget_engine import BudgetEngine
from growth.campaign_engine import CampaignEngine
from growth.core.signal_support import (
    normalize_signal,
    signal_action_type,
    signal_channel,
    signal_confidence,
    signal_expected_value,
    signal_score,
)
from growth.creative_engine import CreativeEngine
from growth.engine_contract import GROWTH_PLAN_KIND, build_package, normalize_payload
from kernel.decision_candidate import DecisionCandidate
from ml.common.feature_vector import FeatureVector
from ml.scoring import RevenuePotentialModel, RiskScoreModel
from observability.growth_events import emit as emit_growth_event


@dataclass(frozen=True)
class GrowthCycle:
    cycle_id: str
    objective: str


@dataclass
class GrowthMemory:
    events: List[dict] = field(default_factory=list)

    def append(self, event: dict) -> None:
        self.events.append(dict(event))


@dataclass(frozen=True)
class StateSnapshot:
    business_id: str
    values: Dict[str, object] = field(default_factory=dict)


class GrowthStateTransition:
    def next_state(self, current_state: str, event: str) -> str:
        return f"{current_state}->{event}"


class OpportunityDetector:
    def detect(self, signals: list[dict]) -> list[dict]:
        return [normalize_signal(signal) for signal in signals if signal_score(signal) > 0.0]


class OpportunityRanker:
    def rank(self, items: list[dict]) -> list[dict]:
        return sorted((normalize_signal(item) for item in items), key=signal_score, reverse=True)


class GrowthPlanBuilder:
    def build(self, opportunities: list[dict]) -> dict:
        normalized = [normalize_signal(item) for item in opportunities]
        return {
            "count": len(normalized),
            "channels": [signal_channel(item) for item in normalized],
        }


class RevenueFeedbackLoop:
    def apply(self, action_result: dict, revenue_delta: float) -> dict:
        return {"action_result": action_result, "revenue_delta": revenue_delta}


CANON_GROWTH_CHANNEL_FEATURE_KEYS: tuple[str, ...] = (
    "intent_strength",
    "expected_value",
    "urgency",
    "historical_roas",
)


class GrowthEngine:
    def __init__(
        self,
        risk_model: RiskScoreModel | None = None,
        revenue_model: RevenuePotentialModel | None = None,
        objective: OptimizationObjective | None = None,
        campaign_engine: CampaignEngine | None = None,
        creative_engine: CreativeEngine | None = None,
        budget_engine: BudgetEngine | None = None,
        opportunity_detector: OpportunityDetector | None = None,
        opportunity_ranker: OpportunityRanker | None = None,
        plan_builder: GrowthPlanBuilder | None = None,
        state_transition: GrowthStateTransition | None = None,
        feedback_loop: RevenueFeedbackLoop | None = None,
        memory: GrowthMemory | None = None,
        event_log: object | None = None,
        channel_bandit: LinearThompsonBandit | None = None,
    ) -> None:
        self._risk_model = risk_model or RiskScoreModel()
        self._revenue_model = revenue_model or RevenuePotentialModel()
        self._objective = objective or OptimizationObjective()
        self._objective.validate()
        self._campaign_engine = campaign_engine or CampaignEngine()
        self._creative_engine = creative_engine or CreativeEngine()
        self._budget_engine = budget_engine or BudgetEngine()
        self._opportunity_detector = opportunity_detector or OpportunityDetector()
        self._opportunity_ranker = opportunity_ranker or OpportunityRanker()
        self._plan_builder = plan_builder or GrowthPlanBuilder()
        self._state_transition = state_transition or GrowthStateTransition()
        self._feedback_loop = feedback_loop or RevenueFeedbackLoop()
        self._memory = memory or GrowthMemory()
        self._event_log = event_log
        self._channel_bandit = channel_bandit or LinearThompsonBandit(
            feature_dim=len(CANON_GROWTH_CHANNEL_FEATURE_KEYS),
            feature_keys=CANON_GROWTH_CHANNEL_FEATURE_KEYS,
            actions=["seo", "ads", "marketplace", "partner"],
        )

    def _normalize_channel_context(self, context: Mapping[str, float]) -> dict[str, float]:
        return {
            key: float(context.get(key, 0.0))
            for key in CANON_GROWTH_CHANNEL_FEATURE_KEYS
        }

    def detect_opportunities(self, signals: list[dict]) -> list[dict]:
        detected = self._opportunity_detector.detect(signals)
        emit_growth_event(self._event_log, "growth_opportunities_detected", {"count": len(detected)})
        return detected

    def rank_opportunities(self, items: list[dict]) -> list[dict]:
        ranked = self._opportunity_ranker.rank(items)
        emit_growth_event(self._event_log, "growth_opportunities_ranked", {"count": len(ranked)})
        return ranked

    def build_opportunity_summary(self, opportunities: list[dict]) -> dict:
        return self._plan_builder.build(opportunities)

    def next_state(self, current_state: str, event: str) -> str:
        return self._state_transition.next_state(current_state, event)

    def apply_revenue_feedback(self, action_result: dict, revenue_delta: float) -> dict:
        feedback = self._feedback_loop.apply(action_result, revenue_delta)
        emit_growth_event(self._event_log, "growth_revenue_feedback_applied", {"revenue_delta": float(revenue_delta)})
        return feedback

    def remember_event(self, event: dict) -> None:
        self._memory.append(event)

    def memory_events(self) -> list[dict]:
        return [dict(event) for event in self._memory.events]

    def snapshot_state(self, business_id: str, values: dict | None = None) -> StateSnapshot:
        return StateSnapshot(business_id=business_id, values=dict(values or {}))

    def start_cycle(self, cycle_id: str) -> GrowthCycle:
        cycle = GrowthCycle(cycle_id=cycle_id, objective=self._objective.name)
        emit_growth_event(self._event_log, "growth_cycle_started", {"cycle_id": cycle.cycle_id, "objective_name": cycle.objective})
        return cycle


    def recommend_channel(self, context: Mapping[str, float]) -> str:
        return self._channel_bandit.select_action(self._normalize_channel_context(context))

    def learn_channel_reward(self, *, channel: str, context: Mapping[str, float], reward: float) -> None:
        self._channel_bandit.update(channel, self._normalize_channel_context(context), float(reward))

    def choose_market_price(
        self,
        *,
        candidate_prices: Sequence[float],
        demand_fn,
        unit_cost: float,
    ) -> dict:
        decision = optimal_price_from_grid(
            candidate_prices=candidate_prices,
            demand_fn=demand_fn,
            unit_cost=float(unit_cost),
        )
        return {
            "price": float(decision.price),
            "expected_profit": float(decision.expected_profit),
            "expected_volume": float(decision.expected_volume),
        }

    def demand_field_score(self, *, x: float, y: float, sources: Sequence[DemandSource]) -> float:
        return float(demand_potential(x=float(x), y=float(y), sources=sources))

    def assemble_opportunities(self, signals: list[dict]) -> list[DecisionCandidate]:
        opportunities: list[DecisionCandidate] = []
        for signal in signals:
            normalized = normalize_signal(signal)
            features = FeatureVector.from_mapping(normalized)
            risk = self._risk_model.score(features.values)
            revenue = self._revenue_model.score(features.values)
            channel = signal_channel(normalized)
            action_type = signal_action_type(normalized)
            expected_value = signal_expected_value(normalized, default=revenue.score)
            score = signal_score({**normalized, "expected_value": expected_value})
            confidence = min(signal_confidence(normalized, default=revenue.confidence), revenue.confidence)
            opportunities.append(
                DecisionCandidate(
                    action_type=action_type,
                    channel=channel,
                    score=score,
                    expected_value=expected_value,
                    confidence=confidence,
                    reasons=[str(normalized.get("summary", "derived_from_signal")), *revenue.reasons, *risk.reasons],
                    payload={
                        "budget_delta": float(normalized.get("budget_delta", 0.0)),
                        "risk_score": risk.score,
                        "signal": normalized,
                        "objective_name": self._objective.name,
                    },
                )
            )
        emit_growth_event(self._event_log, "growth_opportunities_assembled", {"count": len(opportunities)})
        return opportunities

    def assemble_campaign_package(self, payload: dict | None) -> dict:
        return self._campaign_engine.assemble_campaign(normalize_payload(payload))

    def assemble_creative_package(self, payload: dict | None) -> dict:
        return self._creative_engine.assemble_landing(normalize_payload(payload))

    def assemble_budget_package(self, payload: dict | None) -> dict:
        return self._budget_engine.assemble_budget(normalize_payload(payload))

    def assemble_growth_plan(self, payload: dict | None) -> dict:
        normalized = normalize_payload(payload)
        plan = build_package(
            GROWTH_PLAN_KIND,
            normalized,
            objective_name=self._objective.name,
            campaign=self.assemble_campaign_package(normalized),
            creative=self.assemble_creative_package(normalized),
            budget=self.assemble_budget_package(normalized),
        )
        emit_growth_event(self._event_log, "growth_plan_assembled", {"objective_name": self._objective.name})
        return plan


__all__ = [
    "GrowthCycle",
    "GrowthEngine",
    "GrowthMemory",
    "GrowthPlanBuilder",
    "GrowthStateTransition",
    "CANON_GROWTH_CHANNEL_FEATURE_KEYS",
    "OpportunityDetector",
    "OpportunityRanker",
    "RevenueFeedbackLoop",
    "StateSnapshot",
]
