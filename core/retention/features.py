from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.retention.event_types import is_known, normalize_event_type


@dataclass(frozen=True)
class FeatureVector:
    """Small-but-real feature vector used by RetentionEngine.

We DON'T try to compute all 200 here (that would require full event taxonomy).
Instead: we compute the minimum set that makes retention math non-zero,
and we keep the vocabulary stable.
"""

    clicks_d1: int
    listen_seconds_d1: int
    listen_ratio_mean_d1: float
    audio_started_d1: int
    audio_completed_d1: int
    paywall_opened_d7: int
    offer_shown_d7: int
    purchase_success_d30: int
    mood_latest_0_10: int | None
    days_since_last_event: float
    unknown_event_types_d1: int


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def compute_features(
    *,
    events_d1: list[dict[str, Any]],
    events_d7: list[dict[str, Any]],
    events_d30: list[dict[str, Any]],
    latest_mood: int | None,
    now_ms: int,
) -> FeatureVector:
    clicks_d1 = len(events_d1)
    unknown_d1 = 0
    listen_seconds = 0
    listen_ratio_sum = 0.0
    listen_ratio_n = 0
    a_started = 0
    a_completed = 0

    paywall_opened_d7 = 0
    offer_shown_d7 = 0
    purchase_success_d30 = 0

    # --- day 1 parse ---
    for e in events_d1:
        et = normalize_event_type(str(e.get("event_type") or ""))
        if not is_known(et):
            unknown_d1 += 1
        p = e.get("payload") or {}
        if et == "audio_started":
            a_started += 1
        elif et == "audio_completed":
            a_completed += 1
        elif et == "audio_progress":
            pos = float(p.get("pos_s") or p.get("seconds") or 0.0)
            length = float(p.get("length_s") or p.get("length") or 0.0)
            if pos > 0:
                listen_seconds += int(pos)
            if length and length > 0:
                listen_ratio_sum += _clamp(pos / length)
                listen_ratio_n += 1

    # --- 7d parse ---
    for e in events_d7:
        et = normalize_event_type(str(e.get("event_type") or ""))
        if et == "paywall_opened":
            paywall_opened_d7 += 1
        if et == "offer_shown":
            offer_shown_d7 += 1

    # --- 30d parse ---
    for e in events_d30:
        et = normalize_event_type(str(e.get("event_type") or ""))
        if et == "purchase_success":
            purchase_success_d30 += 1

    listen_ratio_mean = listen_ratio_sum / max(1, listen_ratio_n)

    # days since last event (gap proxy)
    last_ts = None
    if events_d30:
        last_ts = int(events_d30[-1].get("timestamp_ms") or 0)
    days_since = (now_ms - last_ts) / 86_400_000.0 if last_ts else 999.0

    return FeatureVector(
        clicks_d1=clicks_d1,
        listen_seconds_d1=listen_seconds,
        listen_ratio_mean_d1=float(listen_ratio_mean),
        audio_started_d1=a_started,
        audio_completed_d1=a_completed,
        paywall_opened_d7=paywall_opened_d7,
        offer_shown_d7=offer_shown_d7,
        purchase_success_d30=purchase_success_d30,
        mood_latest_0_10=latest_mood,
        days_since_last_event=float(days_since),
        unknown_event_types_d1=unknown_d1,
    )
