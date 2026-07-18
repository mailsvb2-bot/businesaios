from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.retention.feature_extractors import activity, audio, mood
from core.retention.feature_extractors.shared import (
    day_key_from_ms,
    day_window_utc,
    pct,
    safe_json,
)


class _EventStore:
    def __init__(self, events: list[dict]) -> None:
        self.events = list(events)

    def iter_events(self, **kwargs):
        start_ms = int(kwargs.get("start_ms") or 0)
        end_ms = int(kwargs.get("end_ms") or 2**63 - 1)
        user_id = kwargs.get("user_id")
        event_type = kwargs.get("event_type")
        for event in self.events:
            ts = int(event.get("timestamp_ms") or 0)
            if not start_ms <= ts <= end_ms:
                continue
            if user_id is not None and event.get("user_id") != user_id:
                continue
            if event_type is not None and event.get("event_type") != event_type:
                continue
            yield event

    def latest_events(self, **kwargs):
        event_type = kwargs.get("event_type")
        user_id = kwargs.get("user_id")
        limit = int(kwargs.get("limit") or 100)
        rows = [
            event
            for event in self.events
            if (event_type is None or event.get("event_type") == event_type)
            and (user_id is None or event.get("user_id") == user_id)
        ]
        rows.sort(key=lambda item: int(item.get("timestamp_ms") or 0), reverse=True)
        return rows[:limit]


def _ms(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp() * 1000)


def test_shared_retention_helpers_cover_boundaries() -> None:
    window = day_window_utc("2026-01-10")
    assert window.end_ms - window.start_ms == 86_400_000
    assert day_key_from_ms(window.start_ms) == "2026-01-10"
    assert safe_json(None) == {}
    assert safe_json({"x": 1}) == {"x": 1}
    assert safe_json('{"x": 2}') == {"x": 2}
    assert safe_json("not-json") == {}
    assert safe_json(7) == {}
    assert pct([], 0.5) == 0.0
    assert pct([5.0, 1.0, 3.0], -1.0) == 1.0
    assert pct([5.0, 1.0, 3.0], 2.0) == 5.0


def test_activity_features_cover_sessions_time_bands_and_commerce(monkeypatch) -> None:
    now = _ms("2026-01-15T12:00:00")
    monkeypatch.setattr(activity.time, "time", lambda: now / 1000.0)

    stored = [
        {"timestamp_ms": _ms("2026-01-10T02:00:00"), "user_id": "u", "event_type": "tariffs_viewed"},
        {"timestamp_ms": _ms("2026-01-10T02:40:00"), "user_id": "u", "event_type": "tariff_selected"},
        {"timestamp_ms": _ms("2026-01-12T08:00:00"), "user_id": "u", "event_type": "payment_created"},
        {"timestamp_ms": _ms("2026-01-12T08:10:00"), "user_id": "u", "event_type": "payment_captured"},
        {"timestamp_ms": _ms("2026-01-13T20:00:00"), "user_id": "u", "event_type": "payment_failed"},
        {"timestamp_ms": _ms("2026-01-14T21:00:00"), "user_id": "u", "event_type": "payment_create_failed"},
        {"timestamp_ms": _ms("2026-01-15T01:00:00"), "user_id": "u", "event_type": "share_clicked"},
        {"timestamp_ms": _ms("2026-01-15T01:00:00") + 100, "user_id": "u", "event_type": "audio_sent"},
        {"timestamp_ms": _ms("2025-12-20T10:00:00"), "user_id": "u", "event_type": "audio_sent"},
        {"timestamp_ms": _ms("2026-01-15T01:00:00"), "user_id": "other", "event_type": "audio_sent"},
    ]
    d1 = [
        {"timestamp_ms": _ms("2026-01-15T01:00:00")},
        {"timestamp_ms": _ms("2026-01-15T01:00:00") + 100},
        {"timestamp_ms": _ms("2026-01-15T01:30:00")},
        {"timestamp_ms": _ms("2026-01-15T08:00:00")},
        {"timestamp_ms": _ms("2026-01-15T20:00:00")},
        {"timestamp_ms": 0},
    ]
    vec: dict[str, float] = {}
    activity.apply_activity_features(
        vec=vec,
        events=d1,
        store=_EventStore(stored),
        tenant_id="t",
        user_id="u",
    )

    assert vec["sessions_d1"] == 4.0
    assert vec["rage_click_score"] > 0.0
    assert vec["night_sessions_share"] > 0.0
    assert vec["morning_sessions_share"] > 0.0
    assert vec["evening_sessions_share"] > 0.0
    assert vec["weekend_sessions_share"] == 0.0
    assert vec["pay_attempt_count"] == 1.0
    assert vec["payment_success_count"] == 1.0
    assert vec["payment_fail_count"] == 2.0
    assert vec["share_click_count_d7"] == 1.0
    assert vec["audio_plays_d30"] == 2.0
    assert activity._sessions_from([], policy=activity.DEFAULT_RETENTION_ACTIVITY_POLICY) == 0
    assert activity._count(stored, "audio_sent") == 3

    empty_vec: dict[str, float] = {}
    activity.apply_activity_features(
        vec=empty_vec,
        events=[],
        store=_EventStore([]),
        tenant_id="t",
        user_id="u",
    )
    assert empty_vec["session_len_mean_s"] == 0.0
    assert empty_vec["active_days_d30"] == 0.0


def test_audio_features_cover_success_fallback_and_parse_errors(monkeypatch) -> None:
    failures: list[str] = []
    monkeypatch.setattr(
        audio,
        "exception_throttled",
        lambda _logger, *, key, msg: failures.append(f"{key}:{msg}"),
    )
    events = [
        {"event_type": "audio_sent"},
        {"event_type": "audio_started", "payload": {"duration_s": "120"}},
        {"event_type": "audio_started", "payload": {"total_s": "bad"}},
        {"event_type": "audio_progress", "payload": {"pos_s": 60, "duration_s": 120}},
        {"event_type": "audio_progress", "payload": {"position_s": "bad", "total_s": "bad"}},
        {"event_type": "audio_completed", "payload": {"total_seconds": 130}},
        {"event_type": "audio_completed", "payload": {"duration_seconds": "bad"}},
        {"event_type": "other"},
    ]
    vec: dict[str, float] = {}
    audio.apply_audio_features(vec=vec, events=events, tenant_id="t", user_id="u")
    assert vec["audio_plays_d1"] == 1.0
    assert vec["audio_started_d1"] == 2.0
    assert vec["audio_completed_d1"] == 2.0
    assert vec["listen_seconds_d1"] == 60.0
    assert 0.4 < vec["listen_ratio_d1"] < 0.5
    assert len(failures) >= 4

    completed_only: dict[str, float] = {}
    audio.apply_audio_features(
        vec=completed_only,
        events=[{"event_type": "audio_completed", "payload": {}}],
        tenant_id="t",
        user_id="u",
    )
    assert completed_only["listen_ratio_d1"] == 1.0

    empty: dict[str, float] = {}
    audio.apply_audio_features(vec=empty, events=[], tenant_id="t", user_id="u")
    assert empty["listen_ratio_d1"] == 0.0


def test_mood_features_cover_buckets_aggregation_and_parse_errors(monkeypatch) -> None:
    assert [mood.mood10_to_bucket(value) for value in (0, 2, 3, 5, 6, 8, 9)] == [1, 1, 2, 2, 3, 3, 4]
    failures: list[str] = []
    monkeypatch.setattr(
        mood,
        "exception_throttled",
        lambda _logger, *, key, msg: failures.append(f"{key}:{msg}"),
    )
    store = _EventStore(
        [
            {"event_type": "mood_logged", "user_id": "u", "timestamp_ms": 5, "payload": {"mood": 1}},
            {"event_type": "mood_logged", "user_id": "u", "timestamp_ms": 4, "payload": {"mood": 4}},
            {"event_type": "mood_logged", "user_id": "u", "timestamp_ms": 3, "payload": {"mood": 7}},
            {"event_type": "mood_logged", "user_id": "u", "timestamp_ms": 2, "payload": {"mood": 10}},
            {"event_type": "mood_logged", "user_id": "u", "timestamp_ms": 1, "payload": {"mood": "bad"}},
        ]
    )
    vec: dict[str, float] = {}
    mood.apply_mood_features(
        vec=vec,
        events=[
            {"event_type": "other"},
            {"event_type": "mood_logged", "payload": {"mood": "bad"}},
            {"event_type": "mood_logged", "payload": {"mood": 12}},
        ],
        store=store,
        tenant_id="t",
        user_id="u",
    )
    assert vec["mood_today"] == 4.0
    assert vec["mood_latest_0_10"] == 10.0
    assert vec["calm_share_d7"] > 0.0
    assert vec["tense_share_d7"] > 0.0
    assert vec["heavy_share_d7"] > 0.0
    assert vec["empty_share_d7"] > 0.0
    assert len(failures) == 2

    empty: dict[str, float] = {}
    mood.apply_mood_features(
        vec=empty,
        events=[],
        store=_EventStore([]),
        tenant_id="t",
        user_id="u",
    )
    assert empty == {}
