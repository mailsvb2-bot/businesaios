from __future__ import annotations

from core.growth.job_lock_eventstore import EventStoreJobLock
from observability.platform.telemetry.event_store import InMemoryEventStore


def test_job_lock_acquire_release():
    es = InMemoryEventStore()
    lock = EventStoreJobLock(store=es, ttl_seconds=300)
    r1 = lock.try_acquire(tenant_id="t1", lock_key="k", owner="o")
    assert r1.acquired
    r2 = lock.try_acquire(tenant_id="t1", lock_key="k", owner="o2")
    assert not r2.acquired
    lock.release(tenant_id="t1", lock_key="k", owner="o")
    r3 = lock.try_acquire(tenant_id="t1", lock_key="k", owner="o3")
    assert r3.acquired
