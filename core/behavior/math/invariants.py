from __future__ import annotations

from core.behavior.math.complex4 import Complex4
from core.behavior.math.vector_ops import clamp, mean


def engagement_from_spinor(psi: Complex4) -> float:
    return clamp(psi.norm_sq())


def coherence_from_spinors(spinors: list[Complex4]) -> float:
    if not spinors:
        return 0.0
    mags = [s.magnitude() for s in spinors]
    flat = [value for row in mags for value in row]
    center = mean(flat)
    variance = mean([(v - center) ** 2 for v in flat])
    return clamp(1.0 - variance)


def anti_field_from_magnitudes(magnitudes: tuple[float, float, float, float]) -> float:
    intent, trust, value, payment = magnitudes
    negative_gap = max(0.0, 1.0 - trust) + max(0.0, 1.0 - value)
    payment_stress = max(0.0, payment - trust)
    return clamp((negative_gap + payment_stress) / 3.0)
