from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


def mse_loss(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """L(θ)= Σ (y - ŷ)^2"""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have same length.")
    if not y_true:
        return 0.0
    s = 0.0
    for yt, yp in zip(y_true, y_pred, strict=False):
        d = float(yt) - float(yp)
        s += d * d
    return s


@dataclass
class GDResult:
    theta: list[float]
    loss: float
    steps: int


def gradient_descent(
    theta0: Sequence[float],
    loss_fn: Callable[[Sequence[float]], float],
    grad_fn: Callable[[Sequence[float]], Sequence[float]],
    *,
    alpha: float = 0.01,
    steps: int = 200,
    tol: float = 1e-10,
) -> GDResult:
    """θ_{t+1} = θ_t - α ∇L(θ_t)"""
    if alpha <= 0:
        raise ValueError("alpha must be > 0.")
    if steps <= 0:
        raise ValueError("steps must be > 0.")

    theta = [float(x) for x in theta0]
    prev = None
    for i in range(steps):
        grad = list(grad_fn(theta))
        if len(grad) != len(theta):
            raise ValueError("grad_fn returned wrong dimension.")
        for j in range(len(theta)):
            theta[j] = theta[j] - alpha * float(grad[j])
        cur = float(loss_fn(theta))
        if prev is not None and abs(prev - cur) <= tol:
            return GDResult(theta=theta, loss=cur, steps=i + 1)
        prev = cur
    return GDResult(theta=theta, loss=float(loss_fn(theta)), steps=steps)
