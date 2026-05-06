from __future__ import annotations

from core.behavior.math.complex4 import Complex4
from core.behavior.math.vector_ops import clamp


def spinor_from_scores(intent: float, trust: float, value: float, payment: float) -> Complex4:
    scores = tuple(clamp(v) for v in (intent, trust, value, payment))
    return Complex4(scores, (0.0, 0.0, 0.0, 0.0)).renormalize()
