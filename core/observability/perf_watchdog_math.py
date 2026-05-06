from __future__ import annotations


def p95(xs: list[int]) -> int:
    if not xs:
        return 0
    ys = sorted(xs)
    i = int(round((len(ys) - 1) * 0.95))
    i = max(0, min(len(ys) - 1, i))
    return int(ys[i])
