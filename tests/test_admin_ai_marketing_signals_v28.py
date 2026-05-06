from __future__ import annotations

from core.admin.ai_marketing import recommend_prices
from core.economics.brain import EconomicBrain, EconomicReward, GrowthPolicy, LTVEstimator, PricingPolicy


def test_recommend_prices_uses_public_brain_signals_only():
    brain = EconomicBrain(LTVEstimator(), PricingPolicy(), GrowthPolicy(), EconomicReward())
    metrics = {"retention": {"users": 10, "active_2d": 1}, "funnel": {"payment_succeeded": 2}}
    plans = [{"title": "Pro", "price": 1000}]
    res = recommend_prices(brain=brain, metrics=metrics, plans=plans)
    assert res["ok"] is True
    assert res["meta"]["action"] == "discount"
