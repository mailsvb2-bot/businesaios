from __future__ import annotations

import math
from bisect import bisect_left
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from .types import DemandObservation

_DEFAULT_ISOELASTIC = (1.0, -1.0)
_DEFAULT_LINEAR = (1.0, -0.01)


class DemandCurveModel(Protocol):
    """Structural contract for deterministic demand prediction."""

    predict_units: Callable[..., float]
    point_elasticity: Callable[..., float]


def _finite(value: float, *, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name}_must_be_finite")
    return number


def _clamp_pos(value: float, eps: float = 1e-12) -> float:
    number = _finite(value, name="demand_value")
    return number if number > eps else float(eps)


def _finite_units(value: float) -> float:
    number = _finite(value, name="demand_prediction")
    return number if number > 0.0 else 0.0


def _stable_mean(values: Sequence[float]) -> float:
    scale = max(abs(value) for value in values)
    if scale == 0.0:
        return 0.0
    return scale * (math.fsum(value / scale for value in values) / len(values))


def _isoelastic_fallback() -> IsoelasticDemandCurve:
    return IsoelasticDemandCurve(*_DEFAULT_ISOELASTIC)


def _linear_fallback() -> LinearDemandCurve:
    return LinearDemandCurve(*_DEFAULT_LINEAR)


def _scaled_least_squares(
    xs: Sequence[float],
    ys: Sequence[float],
    *,
    default_slope: float,
) -> tuple[float, float] | None:
    x_scale = max(abs(value) for value in xs)
    y_scale = max(abs(value) for value in ys)
    x_normalized = [value / x_scale for value in xs] if x_scale else [0.0] * len(xs)
    y_normalized = [value / y_scale for value in ys] if y_scale else [0.0] * len(ys)
    xbar_normalized = math.fsum(x_normalized) / len(xs)
    ybar_normalized = math.fsum(y_normalized) / len(ys)
    dx = [value - xbar_normalized for value in x_normalized]
    dy = [value - ybar_normalized for value in y_normalized]
    centered_x_scale = max(abs(value) for value in dx)
    if centered_x_scale <= 1e-18:
        slope = float(default_slope)
    else:
        centered_y_scale = max(abs(value) for value in dy)
        if centered_y_scale <= 1e-18:
            slope = 0.0
        else:
            scaled_num = math.fsum(
                (x / centered_x_scale) * (y / centered_y_scale)
                for x, y in zip(dx, dy, strict=False)
            )
            scaled_den = math.fsum(
                (x / centered_x_scale) ** 2 for x in dx
            )
            slope = (
                default_slope
                if scaled_den <= 1e-18
                else (y_scale / x_scale)
                * (centered_y_scale / centered_x_scale)
                * (scaled_num / scaled_den)
            )
    xbar = x_scale * xbar_normalized
    ybar = y_scale * ybar_normalized
    intercept = ybar - slope * xbar
    if not math.isfinite(intercept) or not math.isfinite(slope):
        return None
    return float(intercept), float(slope)


@dataclass(frozen=True)
class IsoelasticDemandCurve:
    """Isoelastic demand: Q = a * P^b."""

    a: float
    b: float

    def predict_units(self, *, price: float) -> float:
        p = _clamp_pos(price)
        a = _finite(self.a, name="isoelastic_scale")
        b = _finite(self.b, name="isoelastic_exponent")
        if a <= 0.0:
            raise ValueError("isoelastic_scale_must_be_positive")
        try:
            prediction = a * math.pow(p, b)
        except OverflowError as exc:
            raise ValueError("demand_prediction_must_be_finite") from exc
        return _finite_units(prediction)

    def point_elasticity(self, *, price: float) -> float:
        _clamp_pos(price)
        return _finite(self.b, name="isoelastic_exponent")

    @staticmethod
    def calibrate(observations: Iterable[DemandObservation]) -> IsoelasticDemandCurve:
        xs: list[float] = []
        ys: list[float] = []
        for observation in observations:
            xs.append(math.log(_clamp_pos(observation.price.amount)))
            ys.append(math.log(_clamp_pos(observation.units)))
        if len(xs) < 2:
            return _isoelastic_fallback()
        fit = _scaled_least_squares(xs, ys, default_slope=-1.0)
        if fit is None:
            return _isoelastic_fallback()
        log_scale, exponent = fit
        try:
            scale = math.exp(log_scale)
        except OverflowError:
            return _isoelastic_fallback()
        if not math.isfinite(scale):
            return _isoelastic_fallback()
        if scale <= 0.0:
            scale = 1.0
        return IsoelasticDemandCurve(a=float(scale), b=float(exponent))


@dataclass(frozen=True)
class LinearDemandCurve:
    """Linear demand: Q = max(0, a + b*P)."""

    a: float
    b: float

    def predict_units(self, *, price: float) -> float:
        p = _finite(price, name="demand_price")
        intercept = _finite(self.a, name="linear_intercept")
        slope = _finite(self.b, name="linear_slope")
        return _finite_units(intercept + slope * p)

    def point_elasticity(self, *, price: float) -> float:
        p = _clamp_pos(price)
        q = _clamp_pos(self.predict_units(price=p))
        slope = _finite(self.b, name="linear_slope")
        return _finite(slope * p / q, name="demand_elasticity")

    @staticmethod
    def calibrate(observations: Iterable[DemandObservation]) -> LinearDemandCurve:
        prices: list[float] = []
        units: list[float] = []
        for observation in observations:
            prices.append(_finite(observation.price.amount, name="demand_price"))
            units.append(_finite(observation.units, name="demand_units"))
        if len(prices) < 2:
            return _linear_fallback()
        fit = _scaled_least_squares(prices, units, default_slope=-0.01)
        if fit is None:
            return _linear_fallback()
        intercept, slope = fit
        return LinearDemandCurve(a=intercept, b=slope)


def _collapse_breakpoints(
    rows: Iterable[tuple[float, float, int]],
) -> tuple[tuple[float, float], ...]:
    grouped: dict[float, list[tuple[float, int]]] = {}
    for raw_price, raw_units, raw_weight in rows:
        price = _finite(raw_price, name="demand_price")
        units = _finite(raw_units, name="demand_units")
        weight = int(raw_weight)
        if weight <= 0:
            raise ValueError("demand_breakpoint_weight_must_be_positive")
        grouped.setdefault(price, []).append((units, weight))
    collapsed: list[tuple[float, float]] = []
    for price, entries in sorted(grouped.items()):
        scale = max(abs(units) for units, _ in entries)
        total_weight = sum(weight for _, weight in entries)
        average = (
            0.0
            if scale == 0.0
            else scale
            * (
                math.fsum(
                    (units / scale) * weight for units, weight in entries
                )
                / total_weight
            )
        )
        collapsed.append((price, _finite_units(average)))
    return tuple(collapsed)


@dataclass(frozen=True)
class PiecewiseLinearDemandCurve:
    """Monotone piecewise-linear demand with flat end extrapolation."""

    breakpoints: tuple[tuple[float, float], ...]

    def _sorted(self) -> tuple[tuple[float, float], ...]:
        return _collapse_breakpoints(
            (price, units, 1) for price, units in self.breakpoints
        )

    def predict_units(self, *, price: float) -> float:
        points = self._sorted()
        p = _finite(price, name="demand_price")
        if not points:
            return 0.0
        prices = [point_price for point_price, _ in points]
        index = bisect_left(prices, p)
        if index == 0:
            return points[0][1]
        if index == len(points):
            return points[-1][1]
        if prices[index] == p:
            return points[index][1]
        p0, q0 = points[index - 1]
        p1, q1 = points[index]
        ratio = (p - p0) / (p1 - p0)
        return _finite_units(q0 + ratio * (q1 - q0))

    def point_elasticity(self, *, price: float) -> float:
        p = _clamp_pos(price)
        delta = max(1e-3, 0.01 * p)
        lower = _clamp_pos(self.predict_units(price=p - delta))
        upper = _clamp_pos(self.predict_units(price=p + delta))
        slope = (upper - lower) / (2.0 * delta)
        units = _clamp_pos(self.predict_units(price=p))
        return _finite(slope * p / units, name="demand_elasticity")

    @staticmethod
    def calibrate(
        observations: Sequence[DemandObservation],
        *,
        k: int = 6,
    ) -> PiecewiseLinearDemandCurve:
        if not observations:
            return PiecewiseLinearDemandCurve(breakpoints=tuple())
        samples = sorted(
            (
                _finite(observation.price.amount, name="demand_price"),
                _finite(observation.units, name="demand_units"),
            )
            for observation in observations
        )
        bin_count = max(1, min(len(samples), max(2, int(k))))
        bins: list[list[tuple[float, float]]] = [
            [] for _ in range(bin_count)
        ]
        for index, sample in enumerate(samples):
            bin_index = min(
                bin_count - 1,
                int(index * bin_count / len(samples)),
            )
            bins[bin_index].append(sample)
        rows: list[tuple[float, float, int]] = []
        for bucket in bins:
            weight = len(bucket)
            average_price = _stable_mean([price for price, _ in bucket])
            average_units = _stable_mean([units for _, units in bucket])
            rows.append((average_price, average_units, weight))
        points = list(_collapse_breakpoints(rows))
        units = [quantity for _, quantity in points]
        for index in range(1, len(units)):
            if units[index] > units[index - 1]:
                units[index] = units[index - 1]
        normalized = tuple(
            (points[index][0], units[index]) for index in range(len(points))
        )
        return PiecewiseLinearDemandCurve(breakpoints=normalized)
