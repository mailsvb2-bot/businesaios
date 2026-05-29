from __future__ import annotations

import time
from datetime import UTC, datetime, timezone
from typing import Any, Dict, Iterable, List

from config.scoring_behavior_policy import (
    DEFAULT_RETENTION_ACTIVITY_POLICY,
    RetentionActivityPolicy,
)

from .shared import day_key_from_ms, pct

SESSION_GAP_MS = DEFAULT_RETENTION_ACTIVITY_POLICY.session_gap_ms


def _sessions_from(events: list[dict[str, Any]], *, policy: RetentionActivityPolicy) -> int:
    timestamps = sorted([int(e.get("timestamp_ms") or 0) for e in events if int(e.get("timestamp_ms") or 0) > 0])
    if not timestamps:
        return 0
    n = 1
    prev = timestamps[0]
    for current in timestamps[1:]:
        if int(current - prev) >= int(policy.session_gap_ms):
            n += 1
        prev = current
    return int(n)


def _count(events: Iterable[dict[str, Any]], event_type: str) -> int:
    return int(sum(1 for event in events if str(event.get("event_type")) == str(event_type)))


def apply_activity_features(
    *,
    vec: dict[str, float],
    events: list[dict[str, Any]],
    store: Any,
    tenant_id: str,
    user_id: str,
    policy: RetentionActivityPolicy = DEFAULT_RETENTION_ACTIVITY_POLICY,
) -> None:
    now_ms = int(time.time() * 1000)
    short_window_ms = int(policy.short_window_days) * int(policy.day_ms)
    long_window_ms = int(policy.long_window_days) * int(policy.day_ms)
    start_7d = now_ms - short_window_ms
    day_seen = set()
    n_events_7d = 0
    for event in store.iter_events(tenant_id=tenant_id, start_ms=start_7d, end_ms=now_ms, user_id=user_id):
        n_events_7d += 1
        day_seen.add(day_key_from_ms(int(event.get("timestamp_ms") or 0)))
    vec["clicks_total_d7"] = float(n_events_7d)
    vec["active_days_d7"] = float(len(day_seen))

    events_sorted = sorted(events, key=lambda e: int(e.get("timestamp_ms") or 0))
    timestamps = [int(e.get("timestamp_ms") or 0) for e in events_sorted if int(e.get("timestamp_ms") or 0) > 0]

    sessions_d1 = 0
    session_lengths_s: list[float] = []
    click_intervals_ms: list[int] = []
    if timestamps:
        sessions_d1 = 1
        session_start = timestamps[0]
        prev = timestamps[0]
        for current in timestamps[1:]:
            dt = int(current - prev)
            if dt > 0:
                click_intervals_ms.append(dt)
            if dt >= int(policy.session_gap_ms):
                sessions_d1 += 1
                session_lengths_s.append(max(0.0, float(prev - session_start) / 1000.0))
                session_start = current
            prev = current
        session_lengths_s.append(max(0.0, float(prev - session_start) / 1000.0))

    vec["sessions_d1"] = float(sessions_d1)
    vec["session_len_mean_s"] = float(sum(session_lengths_s) / max(1, len(session_lengths_s))) if session_lengths_s else 0.0
    vec["session_len_p50_s"] = float(pct(session_lengths_s, 0.50)) if session_lengths_s else 0.0
    vec["session_len_p90_s"] = float(pct(session_lengths_s, 0.90)) if session_lengths_s else 0.0

    if click_intervals_ms:
        numeric_intervals = [float(x) for x in click_intervals_ms]
        vec["click_interval_mean_ms"] = float(sum(click_intervals_ms) / max(1, len(click_intervals_ms)))
        vec["click_interval_p50_ms"] = float(pct(numeric_intervals, 0.50))
        vec["click_interval_p90_ms"] = float(pct(numeric_intervals, 0.90))
        short = sum(1 for x in click_intervals_ms if x <= int(policy.rage_click_threshold_ms))
        vec["rage_click_score"] = float(short) / float(max(1, len(click_intervals_ms)))

    if timestamps:
        session_starts = [timestamps[0]]
        prev = timestamps[0]
        for current in timestamps[1:]:
            if int(current - prev) >= int(policy.session_gap_ms):
                session_starts.append(current)
            prev = current
        nss = max(1, len(session_starts))
        night = morning = evening = weekend = 0
        for ts in session_starts:
            dt = datetime.fromtimestamp(ts / 1000.0, tz=UTC)
            h = int(dt.hour)
            wd = int(dt.weekday())
            if wd >= 5:
                weekend += 1
            if h < 6:
                night += 1
            if 6 <= h < 12:
                morning += 1
            if 18 <= h <= 23:
                evening += 1
        vec["night_sessions_share"] = float(night) / float(nss)
        vec["morning_sessions_share"] = float(morning) / float(nss)
        vec["evening_sessions_share"] = float(evening) / float(nss)
        vec["weekend_sessions_share"] = float(weekend) / float(nss)

    start_30d = now_ms - long_window_ms
    events_30d = list(store.iter_events(tenant_id=tenant_id, start_ms=start_30d, end_ms=now_ms, user_id=user_id))
    events_7d = [e for e in events_30d if int(e.get("timestamp_ms") or 0) >= start_7d]

    vec["clicks_total_d30"] = float(len(events_30d))
    vec["clicks_total_d7"] = float(len(events_7d))
    vec["sessions_d7"] = float(_sessions_from(events_7d, policy=policy))
    vec["sessions_d30"] = float(_sessions_from(events_30d, policy=policy))

    day_seen_30 = {day_key_from_ms(int(e.get("timestamp_ms") or 0)) for e in events_30d}
    vec["active_days_d30"] = float(len(day_seen_30))

    ts30 = sorted([int(e.get("timestamp_ms") or 0) for e in events_30d if int(e.get("timestamp_ms") or 0) > 0])
    session_starts30 = []
    if ts30:
        session_starts30 = [ts30[0]]
        prev = ts30[0]
        for current in ts30[1:]:
            if int(current - prev) >= int(policy.session_gap_ms):
                session_starts30.append(current)
            prev = current
    gaps_s = [max(0.0, float(b - a) / 1000.0) for a, b in zip(session_starts30, session_starts30[1:], strict=False)]
    vec["session_gap_mean_s"] = float(sum(gaps_s) / max(1, len(gaps_s))) if gaps_s else 0.0
    vec["session_gap_p50_s"] = float(pct(gaps_s, 0.50)) if gaps_s else 0.0
    if ts30:
        gap_d = float(max(0, now_ms - ts30[-1])) / float(policy.day_ms)
        vec["churn_risk_proxy_gap_d"] = float(gap_d)

    tariffs_viewed_7 = _count(events_7d, "tariffs_viewed")
    tariff_selected_7 = _count(events_7d, "tariff_selected")
    pay_ok_7 = _count(events_7d, "payment_captured") + _count(events_7d, "payment_succeeded")
    vec["pay_attempt_count"] = float(_count(events_30d, "payment_created"))
    vec["payment_success_count"] = float(_count(events_30d, "payment_captured") + _count(events_30d, "payment_succeeded"))
    vec["payment_fail_count"] = float(_count(events_30d, "payment_failed") + _count(events_30d, "payment_create_failed"))
    denom = max(1.0, float(tariffs_viewed_7))
    vec["price_sensitivity_score"] = float(max(0.0, 1.0 - float(tariff_selected_7 + pay_ok_7) / denom))
    vec["share_click_count_d7"] = float(_count(events_7d, "share_clicked"))
    vec["audio_plays_d7"] = float(_count(events_7d, "audio_sent"))
    vec["audio_plays_d30"] = float(_count(events_30d, "audio_sent"))
