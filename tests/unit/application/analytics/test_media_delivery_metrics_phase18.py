from __future__ import annotations

from application.analytics.media_delivery_metrics import MediaDeliveryMetricsProjection


class _EventStore:
    def __init__(self, events):
        self._events = list(events)

    def iter_events(self, *, tenant_id, start_ms, end_ms=None, event_type=None):
        for item in self._events:
            if str(item.get("tenant_id") or "") != str(tenant_id):
                continue
            ts = int(item.get("timestamp_ms") or 0)
            if ts < int(start_ms) or (end_ms is not None and ts > int(end_ms)):
                continue
            yield dict(item)


def _event(*, tenant="tenant-a", ts=1000, ok=True, channel="telegram", kind="voice", finalized=True):
    return {
        "tenant_id": tenant,
        "event_type": "audio_sent",
        "timestamp_ms": ts,
        "payload": {
            "ok": ok,
            "channel": channel,
            "kind": kind,
            "path": "/private/voice.ogg",
            "meta": {
                "delivery_finalized": finalized,
                "delivery_phase": "finalized" if finalized else "accepted_for_delivery",
            },
        },
    }


def test_media_delivery_metrics_classifies_durable_outcomes_without_exposing_source() -> None:
    store = _EventStore(
        [
            _event(ts=1000, ok=True, channel="telegram", kind="voice", finalized=True),
            _event(ts=1100, ok=True, channel="vk", kind="audio", finalized=False),
            _event(ts=1200, ok=False, channel="max", kind="voice", finalized=False),
            {
                "tenant_id": "tenant-a",
                "event_type": "message_sent",
                "timestamp_ms": 1300,
                "payload": {"ok": True},
            },
        ]
    )

    snapshot = MediaDeliveryMetricsProjection(store).build(
        tenant_id="tenant-a",
        window_days=1,
        now_ms=2000,
    )

    assert snapshot.total == 3
    assert snapshot.delivered == 1
    assert snapshot.accepted == 1
    assert snapshot.failed == 1
    assert snapshot.by_channel == {"max": 1, "telegram": 1, "vk": 1}
    assert snapshot.by_kind == {"audio": 1, "voice": 2}
    assert "private" not in repr(snapshot)
    assert "voice.ogg" not in repr(snapshot)


def test_media_delivery_metrics_is_tenant_and_window_scoped() -> None:
    day_ms = 24 * 3600 * 1000
    store = _EventStore(
        [
            _event(tenant="tenant-a", ts=2 * day_ms, ok=True),
            _event(tenant="tenant-b", ts=2 * day_ms, ok=True),
            _event(tenant="tenant-a", ts=1, ok=True),
        ]
    )

    snapshot = MediaDeliveryMetricsProjection(store).build(
        tenant_id="tenant-a",
        window_days=1,
        now_ms=2 * day_ms + 1000,
    )

    assert snapshot.total == 1
    assert snapshot.delivered == 1
    assert snapshot.by_channel == {"telegram": 1}
