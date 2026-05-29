from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Protocol, Tuple

from .types import ConversionObservation


class ConversionModel(Protocol):
    def predict_prob(self, *, price: float) -> float: ...


def _sigmoid(z: float) -> float:
    # Numerically stable sigmoid
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


@dataclass(frozen=True)
class LogisticConversionModel:
    """Logistic conversion model conditioned on price only.

    p(conv|price) = sigmoid(w0 + w1 * price)
    w1 is usually negative.

    Fit uses Newton-Raphson on aggregated binomial observations.
    """

    w0: float
    w1: float
    l2: float = 1e-6

    def predict_prob(self, *, price: float) -> float:
        z = float(self.w0) + float(self.w1) * float(price)
        p = _sigmoid(z)
        # hard clamp to avoid 0/1
        return min(1.0 - 1e-9, max(1e-9, float(p)))

    @staticmethod
    def calibrate(
        observations: Iterable[ConversionObservation],
        *,
        max_iter: int = 50,
        tol: float = 1e-8,
        l2: float = 1e-6,
    ) -> LogisticConversionModel:
        xs: list[float] = []
        ys: list[float] = []
        ns: list[float] = []
        for o in observations:
            n = float(o.opportunities)
            if n <= 0:
                continue
            x = float(o.price.amount)
            y = float(o.conversions)
            y = min(max(0.0, y), n)
            xs.append(x)
            ys.append(y)
            ns.append(n)

        if len(xs) < 2:
            return LogisticConversionModel(w0=-2.0, w1=-0.01, l2=float(l2))

        # Initialize with a conservative slope.
        w0, w1 = -2.0, -0.01

        for _ in range(int(max_iter)):
            # Gradient and Hessian for aggregated binomial log-likelihood.
            g0 = 0.0
            g1 = 0.0
            h00 = l2
            h01 = 0.0
            h11 = l2
            for x, y, n in zip(xs, ys, ns, strict=False):
                z = w0 + w1 * x
                p = _sigmoid(z)
                # grad = X^T (y - n p)
                r = y - n * p
                g0 += r
                g1 += r * x
                # hess = - X^T W X
                w = n * p * (1.0 - p)
                h00 += w
                h01 += w * x
                h11 += w * x * x

            # Solve 2x2 linear system H * delta = grad
            det = h00 * h11 - h01 * h01
            if abs(det) < 1e-18:
                break
            d0 = (g0 * h11 - g1 * h01) / det
            d1 = (g1 * h00 - g0 * h01) / det

            w0_new = w0 + d0
            w1_new = w1 + d1

            if not (math.isfinite(w0_new) and math.isfinite(w1_new)):
                break

            if abs(w0_new - w0) + abs(w1_new - w1) < tol:
                w0, w1 = w0_new, w1_new
                break
            w0, w1 = w0_new, w1_new

        # Guardrails: if slope positive, clamp towards 0 (we expect p↓ with price↑).
        if w1 > 0:
            w1 = -abs(w1) * 0.1

        return LogisticConversionModel(w0=float(w0), w1=float(w1), l2=float(l2))


@dataclass(frozen=True)
class FunnelTransitionModel:
    """First-order funnel dynamics: stage_i -> stage_{i+1} probabilities.

    Stored as (p_add_to_cart, p_checkout, p_purchase), each in [0,1].
    """

    p_add_to_cart: float
    p_checkout: float
    p_purchase: float

    def purchase_prob(self) -> float:
        return float(self.p_add_to_cart) * float(self.p_checkout) * float(self.p_purchase)

    @staticmethod
    def from_counts(*, visits: float, add_to_cart: float, checkouts: float, purchases: float) -> FunnelTransitionModel:
        v = max(1.0, float(visits))
        a = max(0.0, float(add_to_cart))
        c = max(0.0, float(checkouts))
        p = max(0.0, float(purchases))

        p1 = min(1.0, a / v)
        p2 = min(1.0, c / max(1.0, a))
        p3 = min(1.0, p / max(1.0, c))
        return FunnelTransitionModel(p_add_to_cart=float(p1), p_checkout=float(p2), p_purchase=float(p3))
