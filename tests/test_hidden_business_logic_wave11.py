from __future__ import annotations

from core.admin.ai_marketing import generate_copy_variants, recommend_prices
from core.admin.marketing_bandit_read_model import marketing_bandit_stats
from core.creative_intelligence.budget_policy import build_budget_advice
from core.creative_intelligence.models import (
    CreativeIntelligenceSnapshot,
    CreativePnLSnapshot,
    ExperimentConfidenceSnapshot,
    IncrementalitySnapshot,
)
from core.economics.brain import EconomicBrain, EconomicReward, GrowthPolicy, LTVEstimator, PricingPolicy
from core.growth.spend_ledger_event_store import EventStoreSpendLedger
from core.scorers.portfolio import portfolio_rank_score
from application.world_state.creative_state_builder import build_creative_state
from application.world_state.economics_state_builder import build_economics_state


class _BanditStore:
    def iter_events(self, *, tenant_id: str, start_ms: int, end_ms: int):
        yield {
            "event_type": "tariffs_viewed",
            "user_id": "u1",
            "timestamp_ms": start_ms + 1,
            "payload": {"marketing_variant": "a"},
        }
        yield {
            "event_type": "payment_succeeded",
            "user_id": "u1",
            "timestamp_ms": start_ms + 2,
            "payload": {},
        }


class _LedgerStore:
    def latest_events(self, *, tenant_id: str, limit: int, event_types=()):
        return [
            {
                "timestamp_ms": 9999999999999,
                "payload": {
                    "ref": {"platform": "meta", "object_type": "campaign", "object_id": "c1"},
                    "metrics": {"spend": 12.5},
                },
            }
        ]


def _snapshot() -> CreativeIntelligenceSnapshot:
    return CreativeIntelligenceSnapshot(
        creative_id="c1",
        pnl=CreativePnLSnapshot("c1", 100.0, 50.0, 50.0, 0.5, 1.0),
        incrementality=IncrementalitySnapshot("c1", 0.1, 0.7, 0.2, "dr"),
        experiment_confidence=ExperimentConfidenceSnapshot("c1", 0.05, 0.04, 0.96, 0.8),
        expected_value_score=0.4,
        downside_envelope=0.2,
        portfolio_rank_score=0.0,
        explanations=(),
    )


def test_wave11_admin_marketing_and_copy_remain_deterministic() -> None:
    brain = EconomicBrain(LTVEstimator(), PricingPolicy(), GrowthPolicy(), EconomicReward())
    res = recommend_prices(
        brain=brain,
        metrics={"retention": {"users": 10, "active_2d": 1}, "funnel": {"payment_succeeded": 2}},
        plans=[{"title": "Pro", "price": 1000}],
    )
    assert res["ok"] is True
    assert res["items"]
    variants = generate_copy_variants(step_key="offer")
    assert variants["a"] and variants["b"]


def test_wave11_marketing_bandit_and_spend_ledger_keep_owner_consistent_defaults() -> None:
    stats = marketing_bandit_stats(_BanditStore(), now_ms=9999999999999)
    assert stats["tariffs_viewed"]["a"]["alpha"] > 1
    ledger = EventStoreSpendLedger(event_store=_LedgerStore())
    assert ledger.today_spend_minor(tenant_id="t1") == 1250


def test_wave11_creative_budget_portfolio_and_world_state_surfaces_still_work() -> None:
    snapshot = _snapshot()
    advice = build_budget_advice(snapshot=snapshot, total_budget=10000.0)
    assert advice.floor_budget <= advice.target_budget <= advice.ceiling_budget
    assert portfolio_rank_score(snapshot) > 0
    creative_state = build_creative_state((snapshot,))
    economics_state = build_economics_state((snapshot,))
    assert creative_state["creative_count"] == 1.0
    assert economics_state["portfolio_profit_sum"] == 50.0
