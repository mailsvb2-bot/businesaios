from __future__ import annotations

from application.analytics.analytics_materializer import AnalyticsMaterializer
from application.analytics.analytics_snapshot_service import AnalyticsSnapshotService
from application.analytics.distributed_analytics_materializer_lock import PersistentAnalyticsMaterializerLock
from application.analytics.persistent_distributed_analytics_materializer import (
    PersistentDistributedAnalyticsMaterializer,
)
from observability.analytics_snapshot_store import SqliteAnalyticsSnapshotStore
from reliability.distributed_lock import InMemoryDistributedLock


class _BackendAdapter:
    def __init__(self) -> None:
        self._lock = InMemoryDistributedLock()
    def ping(self) -> bool:
        return True
    def acquire(self, **kwargs):
        return self._lock.acquire(**kwargs)
    def renew(self, **kwargs):
        return self._lock.renew(**kwargs)
    def release(self, **kwargs):
        return self._lock.release(**kwargs)
    def get(self, **kwargs):
        return self._lock.get(**kwargs)


class _EventStore:
    def __init__(self, events):
        self._events = list(events)
    def iter_events(self, *, tenant_id, start_ms, end_ms=None, event_type=None):
        for item in self._events:
            if str(item.get('tenant_id') or 'default') != str(tenant_id):
                continue
            yield dict(item)


def test_persistent_materializer_attaches_leadership(tmp_path):
    db_path = tmp_path / 'analytics_snapshots.db'
    events = [{'tenant_id': 'tenant-1', 'event_type': 'offer_shown', 'user_id': 'u1', 'timestamp_ms': 1, 'payload': {}}]
    with SqliteAnalyticsSnapshotStore(str(db_path), tenant_id='tenant-1') as store:
        snapshot_service = AnalyticsSnapshotService(store=store)
        materializer = AnalyticsMaterializer(event_store=_EventStore(events), snapshot_service=snapshot_service)
        lock = PersistentAnalyticsMaterializerLock(lock_backend=_BackendAdapter(), owner_id='node-a')
        distributed = PersistentDistributedAnalyticsMaterializer(materializer=materializer, lock=lock)
        result = distributed.materialize_for_tenant(tenant_id='tenant-1', window_days=30)
    assert 'leadership' in result
    assert result['leadership']['leader_id'] == 'node-a'
