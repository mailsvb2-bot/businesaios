from __future__ import annotations

import pytest

from core.events.read_call import call_iter_events, call_latest_events
from core.telemetry.behavior_read_model import behavior_snapshot
from runtime.messaging_policy_trace.search_store import MessagingPolicyTraceSearchStore


class _LatestModern:
    def latest_events(self, *, tenant_id, user_id, event_types, limit):
        return [
            {'tenant_id': tenant_id, 'user_id': user_id, 'event_type': event_types[0], 'timestamp_ms': 1, 'payload': {'schema': 'behavior_telemetry@v1', 'kind': 'message'}},
        ]


class _LatestLegacy:
    def latest_events(self, *, user_id, event_type, limit):
        return [
            {'tenant_id': 't1', 'user_id': user_id, 'event_type': event_type, 'timestamp_ms': 1, 'payload': {'schema': 'behavior_telemetry@v1', 'kind': 'message'}},
        ]


class _LatestBroken:
    def latest_events(self, *, tenant_id, user_id, event_types, limit):
        raise TypeError('internal bug must not be masked')


class _IterModern:
    def iter_events(self, *, tenant_id, event_types, start_ms, end_ms, limit, user_id=None):
        yield {'tenant_id': tenant_id, 'event_type': event_types[0], 'timestamp_ms': start_ms, 'payload': {}}


class _IterLegacy:
    def iter_events(self, *, tenant_id, event_type, start_ms, end_ms, user_id=None):
        yield {'tenant_id': tenant_id, 'event_type': event_type, 'timestamp_ms': start_ms, 'payload': {}}


class _IterZeroArg:
    def iter_events(self):
        class Record:
            tenant_id = 'tenant-a'
            user_id = 'u1'
            created_at = '2026-03-17'
        return [Record()]


class _IterBroken:
    def iter_events(self, *, tenant_id, event_types, start_ms, end_ms, limit, user_id=None):
        raise TypeError('internal iter bug must not be masked')


def test_call_latest_events_supports_modern_and_legacy_signatures() -> None:
    modern = list(call_latest_events(latest_fn=_LatestModern().latest_events, tenant_id='t1', user_id='u1', event_types=('behavior_telemetry',), limit=5))
    legacy = list(call_latest_events(latest_fn=_LatestLegacy().latest_events, tenant_id='t1', user_id='u1', event_types=('behavior_telemetry',), legacy_event_type='behavior_telemetry', limit=5))
    assert modern[0]['event_type'] == 'behavior_telemetry'
    assert legacy[0]['event_type'] == 'behavior_telemetry'


def test_call_latest_events_does_not_hide_internal_type_errors() -> None:
    with pytest.raises(TypeError, match='internal bug must not be masked'):
        list(call_latest_events(latest_fn=_LatestBroken().latest_events, tenant_id='t1', user_id='u1', event_types=('x',), limit=1))


def test_call_iter_events_supports_modern_legacy_and_zero_arg() -> None:
    modern = list(call_iter_events(iter_fn=_IterModern().iter_events, tenant_id='t1', event_types=('purchase',), start_ms=1, end_ms=2, limit=3))
    legacy = list(call_iter_events(iter_fn=_IterLegacy().iter_events, tenant_id='t1', event_types=('purchase',), start_ms=1, end_ms=2, limit=3))
    zero = list(call_iter_events(iter_fn=_IterZeroArg().iter_events, tenant_id='tenant-a', allow_zero_arg_fallback=True))
    assert modern[0]['event_type'] == 'purchase'
    assert legacy[0]['event_type'] == 'purchase'
    assert zero[0].tenant_id == 'tenant-a'


def test_call_iter_events_does_not_hide_internal_type_errors() -> None:
    with pytest.raises(TypeError, match='internal iter bug must not be masked'):
        list(call_iter_events(iter_fn=_IterBroken().iter_events, tenant_id='t1', event_types=('x',), start_ms=1, end_ms=2, limit=3))


def test_behavior_snapshot_uses_canonical_latest_events_call() -> None:
    snapshot = behavior_snapshot(_LatestLegacy(), tenant_id='t1', user_id='u1', limit=5, lookback_days=1)
    assert snapshot['messages_total'] == 1


def test_trace_search_store_uses_signature_safe_iter_call() -> None:
    store = MessagingPolicyTraceSearchStore(event_store=_IterZeroArg())
    records = store.search_records(tenant_id='tenant-a', user_id='u1', date_from='2026-03-01', date_to='2026-03-31')
    assert len(records) == 1
