from __future__ import annotations

from core.events.log import EventLog
from entrypoints.api.analytics_route_handlers import AnalyticsRouteHandlers


class _SharedEventStore:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, event: dict, commit: bool = True) -> None:
        del commit
        self.events.append(dict(event))

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int,
        end_ms: int | None = None,
        event_type: str | None = None,
    ):
        for event in self.events:
            if str(event.get("tenant_id") or "") != str(tenant_id):
                continue
            timestamp_ms = int(event.get("timestamp_ms") or 0)
            if timestamp_ms < int(start_ms):
                continue
            if end_ms is not None and timestamp_ms > int(end_ms):
                continue
            if event_type is not None and str(event.get("event_type") or "") != str(event_type):
                continue
            yield dict(event)


def test_runtime_audio_outcome_reaches_tenant_scoped_analytics_dashboard() -> None:
    store = _SharedEventStore()
    EventLog(store, tenant="tenant-a").emit(
        event_type="audio_sent",
        source="runtime_effects",
        user_id="user-a",
        decision_id="decision-a",
        correlation_id="correlation-a",
        timestamp_ms=1_800_000_000_000,
        payload={
            "tenant_id": "tenant-a",
            "ok": True,
            "channel": "max",
            "kind": "voice",
            "path": "/private/voice.ogg",
            "meta": {
                "delivery_finalized": True,
                "delivery_phase": "finalized",
            },
        },
    )
    EventLog(store, tenant="tenant-b").emit(
        event_type="audio_sent",
        source="runtime_effects",
        user_id="user-b",
        decision_id="decision-b",
        correlation_id="correlation-b",
        timestamp_ms=1_800_000_000_000,
        payload={
            "tenant_id": "tenant-b",
            "ok": False,
            "channel": "vk",
            "kind": "voice",
            "path": "/private/other.ogg",
            "meta": {
                "delivery_finalized": False,
                "delivery_phase": "accepted_for_delivery",
            },
        },
    )

    result = AnalyticsRouteHandlers(event_store=store).get_dashboard_bundle(
        tenant_id="tenant-a",
        window_days=3650,
    )
    media = result["payload"]["media_delivery"]

    assert media["tenant_id"] == "tenant-a"
    assert media["total"] == 1
    assert media["delivered"] == 1
    assert media["accepted"] == 0
    assert media["failed"] == 0
    assert media["by_channel"] == {"max": 1}
    assert media["by_kind"] == {"voice": 1}
    assert "private" not in repr(media)
    assert "voice.ogg" not in repr(media)
