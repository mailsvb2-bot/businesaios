from __future__ import annotations

from typing import Dict, List, Tuple


def round_step(v: float, step: int) -> int:
    step = max(1, int(step))
    return int(round(float(v) / step) * step)


def clamp_int(x: int, lo: int, hi: int) -> int:
    if x < lo:
        return int(lo)
    if x > hi:
        return int(hi)
    return int(x)


def build_candidates(*, base_price_rub: int, grid_radius_pct: float, grid_step_rub: int, min_price_rub: int, max_price_rub: int, observed_stats: dict[int, tuple[int, int]]) -> list[int]:
    base = int(max(1, base_price_rub))
    lo = int(round(base * (1.0 - float(grid_radius_pct))))
    hi = int(round(base * (1.0 + float(grid_radius_pct))))
    lo = clamp_int(round_step(lo, grid_step_rub), min_price_rub, max_price_rub)
    hi = clamp_int(round_step(hi, grid_step_rub), min_price_rub, max_price_rub)
    if hi < lo:
        lo, hi = hi, lo
    candidates = list(range(int(lo), int(hi) + int(grid_step_rub), int(max(1, grid_step_rub))))
    observed = sorted(observed_stats.keys())
    if observed:
        candidates = [int(p) for p in candidates if int(p) in observed_stats]
    if base not in candidates:
        candidates.append(base)
    return sorted(set(int(p) for p in candidates))
