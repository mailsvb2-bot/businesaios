from __future__ import annotations

from typing import Mapping

from core.behavior.math.complex4 import Complex4
from core.behavior.math.vector_ops import clamp
from core.behavior.operators.operator_keys import ALL_OPERATOR_KEYS

_BASE_SCALES: dict[str, tuple[float, float, float, float]] = {
    "message_open": (1.05, 1.00, 1.01, 0.98),
    "content_engage": (1.06, 1.03, 1.08, 1.00),
    "price_view": (1.00, 0.97, 1.01, 1.05),
    "payment_attempt": (1.01, 0.98, 1.00, 1.10),
    "payment_success": (0.98, 1.06, 1.03, 1.12),
    "refund_signal": (0.92, 0.85, 0.90, 0.88),
    "question_asked": (1.02, 1.03, 1.02, 1.00),
    "rage_click": (0.90, 0.82, 0.88, 0.85),
    "return_after_gap": (1.04, 0.99, 1.01, 0.99),
    "support_relief": (1.01, 1.08, 1.04, 1.00),
}


def supported_operator_keys() -> tuple[str, ...]:
    return ALL_OPERATOR_KEYS


def _resolve_scale(operator_key: str, overrides: Mapping[str, tuple[float, float, float, float]] | None) -> tuple[float, float, float, float]:
    scale = _BASE_SCALES.get(operator_key, (1.0, 1.0, 1.0, 1.0))
    if not overrides:
        return scale
    if operator_key not in overrides:
        return scale
    custom = overrides[operator_key]
    return tuple(clamp(v, 0.75, 1.25) for v in custom)


def apply_operator(
    psi: Complex4,
    operator_key: str,
    overrides: Mapping[str, tuple[float, float, float, float]] | None = None,
) -> Complex4:
    scales = _resolve_scale(operator_key, overrides)
    return psi.component_scale(scales).renormalize()
