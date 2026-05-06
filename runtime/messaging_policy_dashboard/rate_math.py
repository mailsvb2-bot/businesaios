from __future__ import annotations


def safe_rate(numerator: int, denominator: int) -> float:
    den = int(denominator or 0)
    if den <= 0:
        return 0.0
    return round(float(numerator) / float(den), 6)
