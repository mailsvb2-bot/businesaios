from __future__ import annotations

import math

import pytest

from core.economics.world_model.demand_curves import (
    IsoelasticDemandCurve,
    LinearDemandCurve,
    PiecewiseLinearDemandCurve,
    _clamp_pos,
    _collapse_breakpoints,
    _finite,
    _finite_units,
    _scaled_least_squares,
    _stable_mean,
)
from core.economics.world_model.types import DemandObservation, MarketContext, PricePoint

_CONTEXT = MarketContext("tenant", "product")


def _observation(price: float, units: float) -> DemandObservation:
    return DemandObservation(_CONTEXT, PricePoint(price), units)


def test_numeric_helpers_are_fail_closed_and_preserve_finite_values() -> None:
    assert _finite("2.5", name="value") == 2.5
    with pytest.raises(ValueError, match="value_must_be_finite"):
        _finite(float("nan"), name="value")
    assert _clamp_pos(2.0) == 2.0
    assert _clamp_pos(0.0) == 1e-12
    assert _finite_units(2.0) == 2.0
    assert _finite_units(-2.0) == 0.0
    with pytest.raises(ValueError, match="demand_prediction_must_be_finite"):
        _finite_units(float("inf"))
    assert _stable_mean([0.0, 0.0]) == 0.0
    assert _stable_mean([1e308, 1e308]) == 1e308
    assert _stable_mean([1e308, -1e308]) == 0.0


def test_scaled_least_squares_handles_regular_constant_and_degenerate_data() -> None:
    assert _scaled_least_squares([1.0, 2.0], [9.0, 8.0], default_slope=-0.01) == pytest.approx((10.0, -1.0))
    assert _scaled_least_squares([1.0, 1.0], [2.0, 3.0], default_slope=-0.01) == pytest.approx((2.51, -0.01))
    assert _scaled_least_squares([1.0, 2.0], [3.0, 3.0], default_slope=-0.01) == pytest.approx((3.0, 0.0))
    assert _scaled_least_squares([1e308, -1e308], [1e308, -1e308], default_slope=-0.01) == pytest.approx((0.0, 1.0))
    assert _scaled_least_squares([1e308, 5e307], [-1e308, 1e308], default_slope=-0.01) is None
    stable_extreme = _scaled_least_squares(
        [1e308, 1e308],
        [1e308, 1e308],
        default_slope=-0.01,
    )
    assert stable_extreme == pytest.approx((1.01e308, -0.01))


def test_isoelastic_prediction_and_elasticity_preserve_valid_behavior() -> None:
    curve = IsoelasticDemandCurve(a=10.0, b=-1.0)
    assert curve.predict_units(price=2.0) == pytest.approx(5.0)
    assert curve.predict_units(price=0.0) == pytest.approx(1e13)
    assert curve.point_elasticity(price=2.0) == -1.0


@pytest.mark.parametrize("price", [float("nan"), float("inf")])
def test_isoelastic_rejects_nonfinite_price(price: float) -> None:
    curve = IsoelasticDemandCurve(a=1.0, b=-1.0)
    with pytest.raises(ValueError, match="demand_value_must_be_finite"):
        curve.predict_units(price=price)
    with pytest.raises(ValueError, match="demand_value_must_be_finite"):
        curve.point_elasticity(price=price)


def test_isoelastic_rejects_invalid_parameters_and_overflow() -> None:
    with pytest.raises(ValueError, match="isoelastic_scale_must_be_positive"):
        IsoelasticDemandCurve(a=0.0, b=-1.0).predict_units(price=1.0)
    with pytest.raises(ValueError, match="isoelastic_scale_must_be_finite"):
        IsoelasticDemandCurve(a=float("nan"), b=-1.0).predict_units(price=1.0)
    with pytest.raises(ValueError, match="isoelastic_exponent_must_be_finite"):
        IsoelasticDemandCurve(a=1.0, b=float("inf")).predict_units(price=1.0)
    with pytest.raises(ValueError, match="demand_prediction_must_be_finite"):
        IsoelasticDemandCurve(a=1.0, b=-1000.0).predict_units(price=1e-12)


def test_isoelastic_calibration_regular_fallback_and_same_price() -> None:
    assert IsoelasticDemandCurve.calibrate([]) == IsoelasticDemandCurve(1.0, -1.0)
    assert IsoelasticDemandCurve.calibrate([_observation(2.0, 4.0)]) == IsoelasticDemandCurve(1.0, -1.0)
    fitted = IsoelasticDemandCurve.calibrate([_observation(1.0, 10.0), _observation(2.0, 5.0)])
    assert fitted.a == pytest.approx(10.0)
    assert fitted.b == pytest.approx(-1.0)
    same_price = IsoelasticDemandCurve.calibrate([_observation(2.0, 4.0), _observation(2.0, 8.0)])
    assert same_price.b == -1.0
    assert same_price.a > 0.0


def test_isoelastic_calibration_rejects_nonfinite_and_handles_scale_edges(monkeypatch) -> None:
    with pytest.raises(ValueError, match="demand_value_must_be_finite"):
        IsoelasticDemandCurve.calibrate([_observation(float("nan"), 1.0)])
    monkeypatch.setattr(
        "core.economics.world_model.demand_curves._scaled_least_squares",
        lambda *args, **kwargs: None,
    )
    calibrated = IsoelasticDemandCurve.calibrate(
        [_observation(1.0, 1.0), _observation(2.0, 2.0)]
    )
    assert calibrated == IsoelasticDemandCurve(1.0, -1.0)


def test_isoelastic_calibration_handles_exp_overflow_nonfinite_and_underflow(monkeypatch) -> None:
    module = __import__("core.economics.world_model.demand_curves", fromlist=["x"])
    monkeypatch.setattr(module, "_scaled_least_squares", lambda *a, **k: (1000.0, -1.0))
    assert IsoelasticDemandCurve.calibrate([_observation(1, 1), _observation(2, 2)]) == IsoelasticDemandCurve(1.0, -1.0)
    monkeypatch.setattr(module, "_scaled_least_squares", lambda *a, **k: (float("nan"), -1.0))
    assert IsoelasticDemandCurve.calibrate([_observation(1, 1), _observation(2, 2)]) == IsoelasticDemandCurve(1.0, -1.0)
    monkeypatch.setattr(module, "_scaled_least_squares", lambda *a, **k: (-1000.0, -1.0))
    assert IsoelasticDemandCurve.calibrate([_observation(1, 1), _observation(2, 2)]).a == 1.0


def test_linear_prediction_elasticity_and_clamping() -> None:
    curve = LinearDemandCurve(a=10.0, b=-1.0)
    assert curve.predict_units(price=2.0) == 8.0
    assert curve.predict_units(price=20.0) == 0.0
    assert curve.point_elasticity(price=2.0) == pytest.approx(-0.25)
    assert LinearDemandCurve(a=1.0, b=1.0).point_elasticity(price=1.0) == pytest.approx(0.5)


def test_linear_rejects_nonfinite_inputs_parameters_and_results() -> None:
    with pytest.raises(ValueError, match="demand_price_must_be_finite"):
        LinearDemandCurve(1.0, -1.0).predict_units(price=float("nan"))
    with pytest.raises(ValueError, match="linear_intercept_must_be_finite"):
        LinearDemandCurve(float("inf"), -1.0).predict_units(price=1.0)
    with pytest.raises(ValueError, match="linear_slope_must_be_finite"):
        LinearDemandCurve(1.0, float("nan")).predict_units(price=1.0)
    with pytest.raises(ValueError, match="demand_prediction_must_be_finite"):
        LinearDemandCurve(1e308, 1e308).predict_units(price=2.0)


def test_linear_calibration_regular_fallback_constant_and_extreme() -> None:
    assert LinearDemandCurve.calibrate([]) == LinearDemandCurve(1.0, -0.01)
    assert LinearDemandCurve.calibrate([_observation(1.0, 2.0)]) == LinearDemandCurve(1.0, -0.01)
    fitted = LinearDemandCurve.calibrate([_observation(1.0, 9.0), _observation(2.0, 8.0)])
    assert fitted.a == pytest.approx(10.0)
    assert fitted.b == pytest.approx(-1.0)
    same_price = LinearDemandCurve.calibrate([_observation(1.0, 2.0), _observation(1.0, 3.0)])
    assert same_price == pytest.approx(LinearDemandCurve(2.51, -0.01))
    extreme = LinearDemandCurve.calibrate([_observation(1e308, 1e308), _observation(-1e308, -1e308)])
    assert extreme == pytest.approx(LinearDemandCurve(0.0, 1.0))
    unstable = LinearDemandCurve.calibrate([_observation(1e308, -1e308), _observation(5e307, 1e308)])
    assert unstable == LinearDemandCurve(1.0, -0.01)
    with pytest.raises(ValueError, match="demand_units_must_be_finite"):
        LinearDemandCurve.calibrate([_observation(1.0, float("inf"))])


def test_collapse_breakpoints_sorts_averages_clamps_and_validates() -> None:
    collapsed = _collapse_breakpoints(
        [
            (2.0, 8.0, 1),
            (1.0, 10.0, 1),
            (2.0, 4.0, 3),
            (3.0, -2.0, 1),
        ]
    )
    assert collapsed == ((1.0, 10.0), (2.0, 5.0), (3.0, 0.0))
    with pytest.raises(ValueError, match="demand_breakpoint_weight_must_be_positive"):
        _collapse_breakpoints([(1.0, 1.0, 0)])
    with pytest.raises(ValueError, match="demand_price_must_be_finite"):
        _collapse_breakpoints([(float("nan"), 1.0, 1)])
    assert _collapse_breakpoints([(1.0, 0.0, 1), (1.0, 0.0, 2)]) == ((1.0, 0.0),)
    assert _collapse_breakpoints([(1.0, 1e308, 1), (1.0, 1e308, 1)]) == ((1.0, 1e308),)


def test_piecewise_prediction_empty_edges_exact_and_interpolated() -> None:
    assert PiecewiseLinearDemandCurve(()).predict_units(price=1.0) == 0.0
    curve = PiecewiseLinearDemandCurve(((3.0, 0.0), (1.0, 10.0), (2.0, 8.0), (2.0, 4.0)))
    assert curve._sorted() == ((1.0, 10.0), (2.0, 6.0), (3.0, 0.0))
    assert curve.predict_units(price=0.0) == 10.0
    assert curve.predict_units(price=4.0) == 0.0
    assert curve.predict_units(price=2.0) == 6.0
    assert curve.predict_units(price=1.5) == pytest.approx(8.0)
    with pytest.raises(ValueError, match="demand_price_must_be_finite"):
        curve.predict_units(price=float("nan"))


def test_piecewise_elasticity_is_finite_at_interior_and_zero_price() -> None:
    curve = PiecewiseLinearDemandCurve(((1.0, 10.0), (2.0, 5.0), (3.0, 2.0)))
    assert math.isfinite(curve.point_elasticity(price=1.5))
    assert math.isfinite(curve.point_elasticity(price=0.0))


def test_piecewise_calibration_empty_bins_duplicates_and_monotonicity() -> None:
    assert PiecewiseLinearDemandCurve.calibrate([]) == PiecewiseLinearDemandCurve(())
    curve = PiecewiseLinearDemandCurve.calibrate(
        [
            _observation(1.0, 10.0),
            _observation(1.0, 6.0),
            _observation(2.0, 12.0),
            _observation(3.0, 5.0),
        ],
        k=10,
    )
    prices = [price for price, _ in curve.breakpoints]
    units = [quantity for _, quantity in curve.breakpoints]
    assert prices == sorted(set(prices))
    assert units == sorted(units, reverse=True)
    assert curve.breakpoints[0] == (1.0, 8.0)
    with pytest.raises(ValueError, match="demand_price_must_be_finite"):
        PiecewiseLinearDemandCurve.calibrate([_observation(float("inf"), 1.0)])
