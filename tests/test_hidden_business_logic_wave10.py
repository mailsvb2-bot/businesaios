from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from config.reward_bridge_policy import RewardBridgePolicy
from config.strategic_growth_policy import (
    ExperimentsServicePolicy,
    GrowthSignalsPolicy,
    GrowthStrategyServicePolicy,
)
from core.creative_intelligence.models import (
    CreativeIntelligenceSnapshot,
    CreativePnLSnapshot,
    ExperimentConfidenceSnapshot,
    IncrementalitySnapshot,
)
from core.experiments.enums import RolloutDecision
from core.experiments.service import build_empty_result
from core.experiments.types import Experiment
from core.finance.strategic.scenarios.scenario_catalog_data import scenario_definitions
from core.governance.evaluators.profit_metrics import ProfitMetricsService
from core.growth.strategy.contracts import GrowthHypothesisV1, GrowthSignalV1
from core.growth.strategy.service import _default_steps
from core.growth.strategy.signals import build_signals
from core.reward_bridge.future_value_builder import build_future_value
from core.reward_bridge.immediate_reward_builder import build_immediate_reward


@dataclass
class _KPI:
    leads: int = 0
    spend_minor: int = 0
    revenue_minor: int = 0
    profit_minor: int = 0


class _SignalsStore:
    def __init__(self, events: list[dict[str, Any]]):
        self._events = list(events)

    def latest_events(self, *, tenant_id: str, event_types=None, limit: int = 100, **kwargs):
        wanted = None if event_types is None else set(event_types)
        out = [e for e in self._events if e.get("tenant_id") == tenant_id and (wanted is None or e.get("event_type") in wanted)]
        return out[:limit]


class _ProfitStore:
    def __init__(self, *, purchase_events: list[dict[str, Any]], ads_events: list[dict[str, Any]]):
        self._purchase_events = purchase_events
        self._ads_events = ads_events

    def latest_events(self, *, tenant_id: str, event_types=None, limit: int = 100, **kwargs):
        wanted = tuple(event_types or ())
        if wanted == ("purchase_success",):
            return self._purchase_events[:limit]
        if wanted == ("ads_metrics_imported",):
            return self._ads_events[:limit]
        return []


def test_build_empty_result_uses_service_policy_defaults() -> None:
    result = build_empty_result(
        Experiment(experiment_id="exp-1", hypothesis="h", traffic_share=1.0),
        policy=ExperimentsServicePolicy(
            legacy_snapshot_value=2.5,
            legacy_uplift=0.2,
            legacy_p_value=0.7,
        ),
    )
    assert result.control.value == 2.5
    assert result.uplift == 0.2
    assert result.p_value == 0.7
    assert result.rollout_decision == RolloutDecision.HOLD


def test_default_steps_uses_growth_strategy_policy() -> None:
    h = GrowthHypothesisV1(
        hypothesis_id="h1",
        created_ms=1,
        tenant_id="t1",
        stage="retention",
        channel="meta_ads",
        title="title",
        mechanism="mechanism",
        expected_impact="impact",
        effort="low",
        risk="low",
    )
    policy = GrowthStrategyServicePolicy(
        base_steps=("base one", "base two"),
        paid_channel_creative_step="creative pack",
        retention_segment_step="segment users",
        paid_channels=("meta_ads",),
    )
    steps = _default_steps(h, policy=policy)
    assert steps == ("base one", "segment users", "creative pack", "base two")


def test_build_signals_uses_percentage_policy(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.growth.strategy.signals.build_today_kpi",
        lambda store, tenant_id: _KPI(leads=2, spend_minor=100, revenue_minor=200, profit_minor=100),
    )
    now_ms = int(time.time() * 1000)
    events = [
        {"tenant_id": "t1", "user_id": "u1", "timestamp_ms": now_ms, "event_type": "lead_created@v1", "payload": {"channel": "telegram"}},
        {"tenant_id": "t1", "user_id": "u1", "timestamp_ms": now_ms, "event_type": "purchase_completed@v1", "payload": {"channel": "telegram"}},
        {"tenant_id": "t1", "user_id": "u1", "timestamp_ms": now_ms, "event_type": "telegram_message_in@v1", "payload": {"channel": "telegram"}},
    ]
    signals = build_signals(
        _SignalsStore(events),
        tenant_id="t1",
        policy=GrowthSignalsPolicy(percentage_multiplier=10.0, top_channels_limit=1),
    )
    assert isinstance(signals, GrowthSignalV1)
    assert signals.conversion_lead_to_purchase_pct == 5.0
    assert signals.top_channels == ("telegram",)


def test_profit_metrics_service_uses_minor_units_multiplier_policy() -> None:
    service = ProfitMetricsService(
        event_store=_ProfitStore(
            purchase_events=[
                {
                    "timestamp_ms": 2_100_000_000_000,
                    "payload": {"amount": 5},
                }
            ],
            ads_events=[
                {
                    "timestamp_ms": 2_100_000_000_000,
                    "payload": {"metrics": {"spend": 2}},
                }
            ],
        )
    )
    snap = service.profit_lookback(tenant_id="t1", lookback_days=3650)
    assert snap.revenue_minor == 500
    assert snap.ads_spend_minor == 200
    assert snap.profit_minor == 300


def test_reward_bridge_builders_use_policy_weights() -> None:
    snapshot = CreativeIntelligenceSnapshot(
        creative_id="c1",
        pnl=CreativePnLSnapshot(
            creative_id="c1",
            attributed_revenue=100.0,
            total_cost=20.0,
            contribution_profit=80.0,
            contribution_margin_ratio=0.5,
            roi=1.0,
        ),
        incrementality=IncrementalitySnapshot(
            creative_id="c1",
            estimated_effect=0.5,
            confidence_score=0.5,
            downside_risk=0.1,
            method="dr",
        ),
        experiment_confidence=ExperimentConfidenceSnapshot(
            creative_id="c1",
            uplift=0.25,
            p_value=0.1,
            confidence_score=0.9,
            rollout_readiness=0.75,
        ),
        expected_value_score=0.9,
        downside_envelope=0.1,
        portfolio_rank_score=0.5,
    )
    future = build_future_value(snapshot, policy=RewardBridgePolicy(primary_weight=1.0, secondary_weight=0.0, tertiary_weight=0.0))
    immediate = build_immediate_reward(snapshot, policy=RewardBridgePolicy(primary_weight=0.0, secondary_weight=1.0, tertiary_weight=0.0))
    assert future == 0.9
    assert immediate == 0.5


def test_scenario_definitions_return_default_catalog() -> None:
    scenarios = scenario_definitions()
    assert scenarios[0].name == "defense"
    assert scenarios[-1].name == "base"
    assert scenarios[0].revenue_multiplier == Decimal("0.96")
