from __future__ import annotations


def little_law(L: float, lam: float) -> float:
    """Little's law: W = L / λ"""
    lam = float(lam)
    if lam <= 0:
        return 0.0
    return float(L) / lam


def mm1_wait_time(lam: float, mu: float) -> float:
    """M/M/1 expected time in system: W = 1 / (μ - λ), for λ < μ"""
    lam = float(lam)
    mu = float(mu)
    if lam < 0 or mu <= 0:
        raise ValueError("lam must be >=0 and mu must be >0.")
    if lam >= mu:
        return float("inf")
    return 1.0 / (mu - lam)
