from __future__ import annotations

from core.events.read_model_support import (
    best_effort_iter_events,
    best_effort_latest_event,
    best_effort_latest_events,
)


class _Store:
    def latest_event(self, *, tenant_id: str, user_id: str | None = None, event_type: str | None = None):
        return {"timestamp_ms": 7, "event_type": event_type or "x"}

    def latest_events(self, *, tenant_id: str, user_id: str | None = None, event_type: str | None = None, limit: int = 10):
        return [{"timestamp_ms": 1, "event_type": event_type or "x"}] * limit

    def iter_events(self, *, tenant_id: str, event_type: str | None = None, start_ms: int = 0, end_ms: int | None = None, user_id: str | None = None):
        return [{"timestamp_ms": 2, "event_type": event_type or "x"}]


class _BrokenStore:
    def latest_event(self, **kwargs):
        raise RuntimeError("boom")


def test_best_effort_latest_event_uses_supported_signature() -> None:
    ev = best_effort_latest_event(
        event_store=_Store(),
        where='test.latest_event',
        tenant_id='t1',
        user_id='u1',
        event_types=('payment_created',),
        legacy_event_type='payment_created',
    )
    assert ev and ev['event_type'] == 'payment_created'


def test_best_effort_latest_events_and_iter_events_do_not_raise() -> None:
    xs = best_effort_latest_events(
        event_store=_Store(),
        where='test.latest_events',
        tenant_id='t1',
        user_id='u1',
        event_types=('behavior_telemetry',),
        legacy_event_type='behavior_telemetry',
        limit=2,
    )
    ys = best_effort_iter_events(
        event_store=_Store(),
        where='test.iter_events',
        tenant_id='t1',
        user_id='u1',
        event_types=('behavior_telemetry',),
        start_ms=0,
    )
    assert len(xs) == 2
    assert ys and ys[0]['event_type'] == 'behavior_telemetry'


def test_best_effort_latest_event_swallows_failures() -> None:
    assert best_effort_latest_event(
        event_store=_BrokenStore(),
        where='test.broken',
        tenant_id='t1',
        event_types=('x',),
        legacy_event_type='x',
    ) is None
