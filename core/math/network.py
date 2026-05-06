from __future__ import annotations


def metcalfe_value(n_users: int, *, k: float = 1.0) -> float:
    """Metcalfe's law (simple): Value ~ k * n^2"""
    n = max(0, int(n_users))
    return float(k) * float(n * n)
