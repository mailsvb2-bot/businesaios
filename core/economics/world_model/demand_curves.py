from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Protocol, Sequence, Tuple

from .types import DemandObservation


class DemandCurveModel(Protocol):
    """Predict expected units at a given price.

    NOTE: price is assumed to be in the same currency/scale as observations.
    """

    def predict_units(self, *, price: float) -> float: ...
    def point_elasticity(self, *, price: float) -> float: ...


def _clamp_pos(x: float, eps: float = 1e-12) -> float:
    return float(x) if float(x) > eps else float(eps)


@dataclass(frozen=True)
class IsoelasticDemandCurve:
    """Isoelastic demand: Q = a * P^b (b typically < 0).

    Fit is done with log-log least squares on (P, Q).
    """

    a: float
    b: float

    def predict_units(self, *, price: float) -> float:
        p = _clamp_pos(float(price))
        return float(self.a) * (p ** float(self.b))

    def point_elasticity(self, *, price: float) -> float:
        # For isoelastic, elasticity is constant == b
        return float(self.b)

    @staticmethod
    def calibrate(observations: Iterable[DemandObservation]) -> IsoelasticDemandCurve:
        xs: list[float] = []
        ys: list[float] = []
        for o in observations:
            p = _clamp_pos(float(o.price.amount))
            q = _clamp_pos(float(o.units))
            xs.append(math.log(p))
            ys.append(math.log(q))

        if len(xs) < 2:
            # Fallback: minimal non-exploding curve
            return IsoelasticDemandCurve(a=1.0, b=-1.0)

        xbar = sum(xs) / len(xs)
        ybar = sum(ys) / len(ys)
        num = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys, strict=False))
        den = sum((x - xbar) ** 2 for x in xs)
        b = num / den if den > 1e-18 else -1.0
        a = math.exp(ybar - b * xbar)
        # Guardrails: b should be negative for sane demand (but allow weakly).
        if not math.isfinite(b) or not math.isfinite(a):
            return IsoelasticDemandCurve(a=1.0, b=-1.0)
        if a <= 0:
            a = 1.0
        return IsoelasticDemandCurve(a=float(a), b=float(b))


@dataclass(frozen=True)
class LinearDemandCurve:
    """Linear demand: Q = max(0, a + b*P).

    Typically b < 0. Fit by least squares on (P, Q).
    """

    a: float
    b: float

    def predict_units(self, *, price: float) -> float:
        q = float(self.a) + float(self.b) * float(price)
        return float(q) if q > 0.0 else 0.0

    def point_elasticity(self, *, price: float) -> float:
        p = _clamp_pos(float(price))
        q = _clamp_pos(self.predict_units(price=p))
        dqdp = float(self.b)
        return float(dqdp * p / q)

    @staticmethod
    def calibrate(observations: Iterable[DemandObservation]) -> LinearDemandCurve:
        ps: list[float] = []
        qs: list[float] = []
        for o in observations:
            ps.append(float(o.price.amount))
            qs.append(float(o.units))
        if len(ps) < 2:
            return LinearDemandCurve(a=1.0, b=-0.01)

        pbar = sum(ps) / len(ps)
        qbar = sum(qs) / len(qs)
        num = sum((p - pbar) * (q - qbar) for p, q in zip(ps, qs, strict=False))
        den = sum((p - pbar) ** 2 for p in ps)
        b = num / den if den > 1e-18 else -0.01
        a = qbar - b * pbar
        if not math.isfinite(a) or not math.isfinite(b):
            return LinearDemandCurve(a=1.0, b=-0.01)
        return LinearDemandCurve(a=float(a), b=float(b))


@dataclass(frozen=True)
class PiecewiseLinearDemandCurve:
    """Piecewise linear demand curve (monotone non-increasing).

    Represented as breakpoints (price_i, units_i), with linear interpolation.
    Extrapolates flat at ends (clamped to range).
    """

    breakpoints: tuple[tuple[float, float], ...]

    def _sorted(self) -> tuple[tuple[float, float], ...]:
        return tuple(sorted(self.breakpoints, key=lambda x: x[0]))

    def predict_units(self, *, price: float) -> float:
        pts = self._sorted()
        p = float(price)
        if not pts:
            return 0.0
        if p <= pts[0][0]:
            return float(max(0.0, pts[0][1]))
        if p >= pts[-1][0]:
            return float(max(0.0, pts[-1][1]))
        for (p0, q0), (p1, q1) in zip(pts, pts[1:], strict=False):
            if p0 <= p <= p1:
                t = (p - p0) / (p1 - p0) if p1 != p0 else 0.0
                q = q0 + t * (q1 - q0)
                return float(max(0.0, q))
        return float(max(0.0, pts[-1][1]))

    def point_elasticity(self, *, price: float) -> float:
        # Numerical derivative on the interpolated curve.
        p = _clamp_pos(float(price))
        dp = max(1e-3, 0.01 * p)
        q0 = _clamp_pos(self.predict_units(price=p - dp))
        q1 = _clamp_pos(self.predict_units(price=p + dp))
        dqdp = (q1 - q0) / (2.0 * dp)
        q = _clamp_pos(self.predict_units(price=p))
        return float(dqdp * p / q)

    @staticmethod
    def calibrate(observations: Sequence[DemandObservation], *, k: int = 6) -> PiecewiseLinearDemandCurve:
        """Fit by binning price into <=k quantiles and taking avg units."""

        if not observations:
            return PiecewiseLinearDemandCurve(breakpoints=tuple())

        obs = sorted(observations, key=lambda o: float(o.price.amount))
        k = max(2, int(k))
        bins: list[list[DemandObservation]] = [[] for _ in range(k)]
        for i, o in enumerate(obs):
            idx = min(k - 1, int(i * k / max(1, len(obs))))
            bins[idx].append(o)

        pts: list[tuple[float, float]] = []
        for b in bins:
            if not b:
                continue
            p = sum(float(o.price.amount) for o in b) / len(b)
            q = sum(float(o.units) for o in b) / len(b)
            pts.append((float(p), float(q)))

        # Enforce monotone non-increasing with isotonic-like pass.
        pts.sort(key=lambda x: x[0])
        qs = [q for _, q in pts]
        for i in range(1, len(qs)):
            if qs[i] > qs[i - 1]:
                qs[i] = qs[i - 1]
        pts = [(pts[i][0], qs[i]) for i in range(len(pts))]
        return PiecewiseLinearDemandCurve(breakpoints=tuple(pts))
