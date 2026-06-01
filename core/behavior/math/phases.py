from __future__ import annotations

from core.behavior.math.vector_ops import clamp, mean


def phase_stability(phases: list[tuple[float, float, float, float]]) -> float:
    if len(phases) < 2:
        return 1.0
    deltas: list[float] = []
    prev = phases[0]
    for current in phases[1:]:
        for a, b in zip(prev, current, strict=False):
            deltas.append(abs(b - a))
        prev = current
    avg_delta = mean(deltas)
    return clamp(1.0 - avg_delta / 3.1415926535)


def oscillation_score(phases: list[tuple[float, float, float, float]]) -> float:
    if len(phases) < 3:
        return 0.0
    changes = 0
    samples = 0
    for idx in range(2, len(phases)):
        for a, b, c in zip(phases[idx - 2], phases[idx - 1], phases[idx], strict=False):
            left = b - a
            right = c - b
            if left == 0.0 or right == 0.0:
                continue
            samples += 1
            if left * right < 0.0:
                changes += 1
    if samples == 0:
        return 0.0
    return clamp(changes / float(samples))
