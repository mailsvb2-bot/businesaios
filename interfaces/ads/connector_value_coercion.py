from __future__ import annotations

from typing import Any


def as_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def as_float(value: Any, *, default: float = 0.0, scale: float = 1.0) -> float:
    try:
        return float(value) / float(scale)
    except Exception:
        return float(default)


def as_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def safe_ratio(
    numerator: float | None,
    denominator: int | None,
) -> float | None:
    if numerator is None or denominator is None or int(denominator) <= 0:
        return None
    try:
        return float(numerator) / float(denominator)
    except Exception:
        return None
