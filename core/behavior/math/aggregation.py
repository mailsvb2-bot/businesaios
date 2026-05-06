from __future__ import annotations

from core.behavior.math.complex4 import Complex4


def aggregate_spinors(spinors: list[Complex4]) -> Complex4:
    if not spinors:
        return Complex4.zero()
    result = Complex4.zero()
    for spinor in spinors:
        result = result.add(spinor)
    return result.scale(1.0 / float(len(spinors))).renormalize()


def weighted_aggregate_spinors(spinors: list[tuple[Complex4, float]]) -> Complex4:
    if not spinors:
        return Complex4.zero()
    total_weight = 0.0
    result = Complex4.zero()
    for spinor, weight in spinors:
        safe_weight = max(0.0, weight)
        total_weight += safe_weight
        result = result.add(spinor.scale(safe_weight))
    if total_weight <= 0.0:
        return Complex4.zero()
    return result.scale(1.0 / total_weight).renormalize()
