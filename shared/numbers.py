from __future__ import annotations

import math


def coerce_float(value: object, default: float = 0.0, *, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = float(default)
    if not math.isfinite(numeric):
        numeric = float(default)
    if minimum is not None:
        numeric = max(float(minimum), numeric)
    if maximum is not None:
        numeric = min(float(maximum), numeric)
    return numeric


def coerce_int(value: object, default: int = 0, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = int(default)
    if minimum is not None:
        numeric = max(int(minimum), numeric)
    if maximum is not None:
        numeric = min(int(maximum), numeric)
    return numeric
