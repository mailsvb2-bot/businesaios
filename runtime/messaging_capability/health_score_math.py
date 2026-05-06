from __future__ import annotations


def next_health_score(*, previous: float, ok: bool, blocked: bool) -> float:
    value = float(previous)
    if blocked:
        value = min(value, 0.20)
    elif ok:
        value = min(1.0, value + 0.10)
    else:
        value = max(0.0, value - 0.25)
    return round(max(0.0, min(1.0, value)), 4)
