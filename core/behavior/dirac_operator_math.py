"""Pure Dirac-Ring math. No catalogs, policies, or event handling."""

from __future__ import annotations

from typing import Tuple

from core.behavior.complex4 import EPS, Complex4


def clamp01(x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return float(x)


def clamp(x: float, lo: float, hi: float) -> float:
    x = float(x)
    if x < lo:
        return float(lo)
    if x > hi:
        return float(hi)
    return float(x)


def apply_diag_impulse(
    psi: Complex4,
    d: tuple[float, float, float, float],
    phase_gain: float,
) -> Complex4:
    """Apply diagonal impulse + small phase rotation."""
    re = list(psi.re)
    im = list(psi.im)
    import math
    for i in range(4):
        re[i] = float(re[i] + float(d[i]))
        theta = float(phase_gain) * float(d[i])
        c, s = math.cos(theta), math.sin(theta)
        r, j = re[i], im[i]
        re[i] = float(r * c - j * s)
        im[i] = float(r * s + j * c)
    nxt = Complex4(tuple(re), tuple(im))
    if nxt.norm2() <= EPS:
        return nxt
    return nxt.renormalize(target_norm=1.0)


def mix(psi: Complex4, i: int, j: int, k: float) -> Complex4:
    re = list(psi.re)
    im = list(psi.im)
    xi, xj = float(re[i]), float(re[j])
    yi, yj = float(im[i]), float(im[j])
    re[i] = float(xi + k * xj)
    re[j] = float(xj + k * xi)
    im[i] = float(yi + k * yj)
    im[j] = float(yj + k * yi)
    nxt = Complex4(tuple(re), tuple(im))
    if nxt.norm2() <= EPS:
        return nxt
    return nxt.renormalize(target_norm=1.0)


__all__ = ["clamp01", "clamp", "apply_diag_impulse", "mix"]
