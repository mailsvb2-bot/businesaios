"""Retention math: hazard (churn risk) and readiness.

This is deliberately **minimal, deterministic, and production-safe**:
- pure functions
- bounded outputs [0..1]
- no hidden model weights

It is a computable translation of the chat spec:
- risk/hazard affects the exponential tail of LTV
- offers are triggered by *state*, not by clock time
"""

from __future__ import annotations

import math

def sigmoid(x: float) -> float:
    # stable-ish sigmoid for moderate x
    return 1.0 / (1.0 + math.exp(-x))


def churn_hazard(features: dict[str, float]) -> float:
    """Probability proxy of churn within the next ~7 days.

    Uses a small set of high-signal features; the rest of the 200-dim vector
    is reserved for future training/feature selection.
    """

    mood = float(features.get("mood_today", 2.0) or 2.0)  # 1..4
    heavy = float(features.get("heavy_share_d7", 0.0) or 0.0)
    empty = float(features.get("empty_share_d7", 0.0) or 0.0)
    listen_s = float(features.get("listen_seconds_total_d1", 0.0) or 0.0)
    bounce = float(features.get("paywall_bounce_rate", 0.0) or 0.0)
    gap_d = float(features.get("churn_risk_proxy_gap_d", 0.0) or 0.0)

    # Normalizations
    mood_n = max(0.0, min((mood - 1.0) / 3.0, 1.0))  # worse -> 1
    listen_n = max(0.0, min(listen_s / 1500.0, 1.0))  # 25 min proxy
    gap_n = max(0.0, min(gap_d / 7.0, 1.0))

    x = (
        2.2 * mood_n
        + 1.5 * heavy
        + 1.5 * empty
        + 1.2 * gap_n
        + 0.7 * bounce
        - 1.0 * listen_n
    )
    return max(0.0, min(sigmoid(x), 1.0))


def readiness(features: dict[str, float]) -> float:
    """Readiness-to-buy proxy in [0..1]."""

    calm = float(features.get("calm_share_d7", 0.0) or 0.0)
    listen_ratio = float(features.get("listen_ratio_mean", 0.0) or 0.0)
    streak = float(features.get("streak_len_days", 0.0) or 0.0)
    bounce = float(features.get("paywall_bounce_rate", 0.0) or 0.0)
    hazard = float(features.get("churn_hazard_estimate", 0.0) or 0.0)

    streak_n = max(0.0, min(streak / 7.0, 1.0))

    x = 2.0 * calm + 1.2 * listen_ratio + 0.3 * streak_n - 1.0 * bounce - 1.5 * hazard
    return max(0.0, min(sigmoid(x), 1.0))
