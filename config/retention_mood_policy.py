from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class RetentionMoodPolicy:
    calm_upper_inclusive: float = 2.0
    tense_upper_inclusive: float = 5.0
    heavy_upper_inclusive: float = 8.0
    latest_events_limit: int = 7
    mood_min: float = 0.0
    mood_max: float = 10.0


DEFAULT_RETENTION_MOOD_POLICY = RetentionMoodPolicy()
