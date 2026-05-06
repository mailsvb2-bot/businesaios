from __future__ import annotations

import math

from core.economics.world_model.conversion import LogisticConversionModel
from core.economics.world_model.demand_curves import IsoelasticDemandCurve, PiecewiseLinearDemandCurve
from core.economics.world_model.serialize import pricing_world_model_from_dict, pricing_world_model_to_dict
from core.economics.world_model.types import ConversionObservation, DemandObservation, MarketContext, PricePoint
from core.economics.world_model.world_model import PricingWorldModel
from core.economics.world_model.world_state import WorldModelInput


def test_isoelastic_fit_recovers_sign():
    ctx = MarketContext(tenant_id="t1", product_id="p1", currency="USD", dow=0)
    obs = []
    # Synthetic Q = 1000 * P^-1.5
    for p in [10, 20, 30, 40, 50]:
        q = 1000 * (p ** -1.5)
        obs.append(DemandObservation(context=ctx, price=PricePoint(p), units=q))
    m = IsoelasticDemandCurve.calibrate(obs)
    assert m.a > 0
    assert m.b < 0
    assert abs(m.b - (-1.5)) < 0.2  # loose, no numpy


def test_piecewise_fit_monotone():
    ctx = MarketContext(tenant_id="t1", product_id="p1", currency="USD", dow=1)
    obs = []
    for p, q in [(10, 100), (20, 70), (30, 80), (40, 50)]:
        obs.append(DemandObservation(context=ctx, price=PricePoint(p), units=q))
    m = PiecewiseLinearDemandCurve.calibrate(obs, k=3)
    pts = list(m.breakpoints)
    assert len(pts) >= 2
    qs = [q for _, q in pts]
    # monotone non-increasing
    assert all(qs[i] <= qs[i - 1] +1e-9 for i in range(1, len(qs)))


def test_logistic_fit_predicts_reasonable_probs():
    ctx = MarketContext(tenant_id="t1", product_id="p1", currency="USD")
    obs = []
    # conversion drops with price
    for p, conv, n in [(10, 50, 100), (20, 30, 100), (30, 15, 100), (40, 8, 100)]:
        obs.append(ConversionObservation(context=ctx, price=PricePoint(p), conversions=conv, opportunities=n))
    m = LogisticConversionModel.calibrate(obs, max_iter=50)
    p10 = m.predict_prob(price=10)
    p40 = m.predict_prob(price=40)
    assert 0 < p40 < p10 < 1
    assert m.w1 <= 0  # expected negative slope


def test_world_model_serialization_roundtrip():
    m = PricingWorldModel.default()
    d = pricing_world_model_to_dict(m)
    m2 = pricing_world_model_from_dict(d)
    d2 = pricing_world_model_to_dict(m2)
    assert d2.get("kind") == "pricing_world_model@v1"


def test_world_model_build_outputs_profit_and_revenue():
    ctx = MarketContext(tenant_id="t1", product_id="p1", currency="USD", dow=2)
    m = PricingWorldModel.default()
    ws = m.build(WorldModelInput(context=ctx, current_price=20.0, marginal_cost=5.0))
    assert math.isfinite(ws.expected_revenue)
    assert math.isfinite(ws.expected_profit)
