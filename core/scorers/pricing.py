from __future__ import annotations

"""Canonical pricing RL scoring helpers."""

import math


def softmax_probs(values: list[float], *, temperature: float) -> list[float]:
    if not values:
        return []
    t = float(temperature)
    if not (t > 0.0):
        probs = [0.0 for _ in values]
        probs[max(range(len(values)), key=lambda i: values[i])] = 1.0
        return probs
    m = max(values)
    exps = [math.exp((v - m) / t) for v in values]
    s = sum(exps) or 1.0
    return [float(x) / float(s) for x in exps]


def sample_index(rng, probs: list[float]) -> int:
    r = float(rng.random())
    c = 0.0
    for i, p in enumerate(probs):
        c += float(p)
        if r <= c:
            return int(i)
    return int(len(probs) - 1)


def choose_probabilities(*, exploration: str, expected_revenue: list[float], epsilon: float, temperature: float) -> list[float]:
    mode = str(exploration or "softmax_v1").strip().lower()
    if mode == "epsilon_greedy_v1":
        best_i = max(range(len(expected_revenue)), key=lambda i: expected_revenue[i])
        n = len(expected_revenue)
        eps = min(max(float(epsilon), 0.0), 1.0)
        probs = [eps / float(n) for _ in range(n)]
        probs[best_i] += 1.0 - eps
        return probs
    return softmax_probs(expected_revenue, temperature=float(temperature))


def choose_candidate(scored: list[dict]) -> dict | None:
    if not scored:
        return None
    top = dict(scored[0] or {})
    candidate = top.get("candidate")
    return dict(candidate) if isinstance(candidate, dict) else None
