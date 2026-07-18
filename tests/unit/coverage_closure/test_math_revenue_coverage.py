from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.analytics.revenue_metrics import (
    aggregate_revenue_metrics,
    make_yesterday_window,
)
from core.causal.math_utils import (
    _matmul,
    _solve_gauss_jordan,
    _transpose,
    clip,
    dot,
    linear_regression_fit,
    mean,
    sigmoid,
    stderr_of_mean,
    variance,
)
from core.contracts.event_types import (
    OFFER_CLICKED,
    OFFER_SHOWN,
    PURCHASE_FAILED,
    PURCHASE_SUCCESS,
)
from core.economics.world_model.conversion import (
    FunnelTransitionModel,
    LogisticConversionModel,
)
from core.economics.world_model.types import (
    ConversionObservation,
    MarketContext,
    PricePoint,
)
from core.math.advanced_models.optimal_transport import solve_capacity_transport
from core.math.pagerank import pagerank


def test_pagerank_transport_and_linear_algebra_cover_errors_and_convergence() -> None:
    with pytest.raises(ValueError):
        pagerank({"a": ["b"]}, d=-0.1)
    with pytest.raises(ValueError):
        pagerank({"a": ["b"]}, d=1.1)
    assert pagerank({}) == {}
    ranks = pagerank({"a": ["b"], "b": [], "c": ["a", "b"]}, iters=200)
    assert set(ranks) == {"a", "b", "c"}
    assert sum(ranks.values()) == pytest.approx(1.0)

    with pytest.raises(ValueError):
        solve_capacity_transport([], [], [])
    with pytest.raises(ValueError):
        solve_capacity_transport([[1]], [1, 2], [1])
    with pytest.raises(ValueError):
        solve_capacity_transport([[1]], [1], [1, 2])
    with pytest.raises(ValueError):
        solve_capacity_transport([[1]], [2], [1])
    transport = solve_capacity_transport([[1, 5], [2, 1]], [3, 2], [2, 3])
    assert transport.total_cost == pytest.approx(9.0)
    assert sum(sum(row) for row in transport.allocation) == pytest.approx(5.0)

    assert mean([]) == 0.0
    assert mean([1, 3]) == 2.0
    assert variance([]) == 0.0
    assert variance([1]) == 0.0
    assert variance([1, 3]) == 2.0
    assert stderr_of_mean([1]) == 0.0
    assert stderr_of_mean([1, 3]) == pytest.approx(1.0)
    assert sigmoid(100) > 0.99
    assert sigmoid(-100) < 0.01
    assert _transpose([]) == []
    assert _transpose([[1, 2], [3, 4]]) == [[1, 3], [2, 4]]
    assert _matmul([[1, 2]], [[3], [4]]) == [[11.0]]
    assert _solve_gauss_jordan([[0, 1], [2, 3]], [1, 5]) == pytest.approx([1, 1])
    assert _solve_gauss_jordan([[1, 1], [2, 2]], [1, 2]) == [0.0, 0.0]
    assert linear_regression_fit([], []).coef == []
    with pytest.raises(ValueError):
        linear_regression_fit([[1]], [])
    fit = linear_regression_fit([[1, 0], [1, 1], [1, 2]], [1, 3, 5])
    assert fit.coef == pytest.approx([1, 2])
    assert dot([1, 2], [3, 4, 5]) == 11.0
    assert clip(-1, 0, 2) == 0.0
    assert clip(3, 0, 2) == 2.0


def test_conversion_models_cover_fallback_fit_and_funnel_clamps() -> None:
    context = MarketContext(tenant_id="t", product_id="p")
    one = [
        ConversionObservation(
            context=context,
            price=PricePoint(100),
            conversions=2,
            opportunities=10,
        )
    ]
    fallback = LogisticConversionModel.calibrate(one)
    assert fallback.w0 == -2.0
    assert fallback.predict_prob(price=100) > 0.0

    observations = [
        ConversionObservation(context=context, price=PricePoint(100), conversions=1, opportunities=10),
        ConversionObservation(context=context, price=PricePoint(200), conversions=4, opportunities=10),
        ConversionObservation(context=context, price=PricePoint(300), conversions=9, opportunities=10),
        ConversionObservation(context=context, price=PricePoint(400), conversions=-3, opportunities=0),
    ]
    model = LogisticConversionModel.calibrate(observations, max_iter=20)
    assert model.w1 <= 0.0
    assert 0.0 < model.predict_prob(price=-10_000) < 1.0
    assert 0.0 < model.predict_prob(price=10_000) < 1.0

    unchanged = LogisticConversionModel.calibrate(observations, max_iter=0)
    assert unchanged.w0 == -2.0
    funnel = FunnelTransitionModel.from_counts(
        visits=0,
        add_to_cart=20,
        checkouts=30,
        purchases=40,
    )
    assert funnel.p_add_to_cart == 1.0
    assert funnel.p_checkout == 1.0
    assert funnel.p_purchase == 1.0
    assert funnel.purchase_prob() == 1.0


def test_revenue_metrics_cover_timestamp_shapes_and_zero_denominators() -> None:
    now = datetime(2026, 1, 15, 12, tzinfo=UTC)
    window = make_yesterday_window(now)
    inside = int(datetime(2026, 1, 14, 10, tzinfo=UTC).timestamp())
    events = [
        "not-a-dict",
        {"event_type": OFFER_SHOWN, "timestamp": inside},
        {"event_type": OFFER_SHOWN, "timestamp_ms": inside * 1000},
        {"event_type": OFFER_CLICKED, "created_at": "2026-01-14T11:00:00Z"},
        {"event_type": PURCHASE_SUCCESS, "time": "2026-01-14T12:00:00+00:00", "payload": {"amount": 50, "offer_id": "a"}},
        {"event_type": PURCHASE_SUCCESS, "ts": inside, "payload": {"amount": 70, "offer_id": "b"}},
        {"event_type": PURCHASE_FAILED, "timestamp": inside},
        {"event_type": OFFER_CLICKED, "timestamp": "bad"},
        {"event_type": OFFER_CLICKED, "timestamp": int(window.end_utc.timestamp())},
    ]
    metrics = aggregate_revenue_metrics(events=events, window=window)
    assert metrics["impressions"] == 2
    assert metrics["clicks"] == 1
    assert metrics["purchases_success"] == 2
    assert metrics["purchases_failed"] == 1
    assert metrics["revenue"] == 120.0
    assert metrics["top_offer_id"] == "b"

    zero = aggregate_revenue_metrics(events=[], window=window)
    assert zero["ctr"] == 0.0
    assert zero["cr"] == 0.0
    assert zero["arpu"] == 0.0
    assert zero["top_offer_id"] is None
