from __future__ import annotations

import math
from typing import Dict


def sigmoid(x: float) -> float:
    if x >= 60:
        return 1.0
    if x <= -60:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def estimate_hazard(features: Dict[str, float]) -> float:
    mood = features.get("mood_latest_0_10")
    mood_bad = 0.5
    if mood is not None:
        mood_bad = 1.0 - max(0.0, min(float(mood) / 10.0, 1.0))
    listen_ratio = float(features.get("listen_ratio_d1", features.get("audio_completion_rate", 0.0)))
    listen_bad = 1.0 - max(0.0, min(listen_ratio, 1.0))
    gap = max(0.0, float(features.get("inactivity_days", 0.0)))
    gap_n = min(gap / 7.0, 1.0)
    clicks = max(0.0, float(features.get("clicks_total_d1", 0.0)))
    clicks_n = min(clicks / 25.0, 1.0)
    x = 1.4 * gap_n + 1.0 * mood_bad + 0.8 * listen_bad - 0.6 * clicks_n - 0.3
    return max(0.0, min(1.0, float(sigmoid(x))))


def estimate_readiness(features: Dict[str, float]) -> float:
    sessions_7d = max(0.0, float(features.get("sessions_d7", features.get("active_days_d7", 0.0))))
    sessions_n = min(sessions_7d / 7.0, 1.0)
    listen_ratio = float(features.get("listen_ratio_d1", features.get("audio_completion_rate", 0.0)))
    listen_n = max(0.0, min(listen_ratio, 1.0))
    clicks = max(0.0, float(features.get("clicks_total_d1", 0.0)))
    clicks_n = min(clicks / 25.0, 1.0)
    gap = max(0.0, float(features.get("inactivity_days", 0.0)))
    gap_n = min(gap / 7.0, 1.0)
    x = 1.2 * sessions_n + 1.0 * listen_n + 0.6 * clicks_n - 1.1 * gap_n - 0.2
    return max(0.0, min(1.0, float(sigmoid(x))))


def should_suppress_marketing(*, hazard: float, readiness: float) -> bool:
    try:
        h = float(hazard)
        r = float(readiness)
    except Exception:
        return True
    return (h >= 0.80) or (r <= 0.20)
