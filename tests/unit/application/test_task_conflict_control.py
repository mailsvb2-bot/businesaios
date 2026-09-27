from __future__ import annotations

import threading
from datetime import timedelta

from application.task.registry import TaskConflictController
from reliability.distributed_lock import InMemoryDistributedLock, utc_now


def test_task_conflict_lock_allows_only_one_concurrent_task() -> None:
    controller = TaskConflictController(distributed_lock=InMemoryDistributedLock())
    barrier = threading.Barrier(3)
    results: list[bool] = []
    groups = []

    def contender(task_id: str) -> None:
        barrier.wait()
        try:
            group = controller.acquire(
                tenant_id="tenant-1",
                business_id="business-1",
                task_id=task_id,
                conflict_keys=("ledger",),
            )
        except RuntimeError:
            results.append(False)
        else:
            groups.append(group)
            results.append(True)

    threads = [threading.Thread(target=contender, args=(name,)) for name in ("a", "b")]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5)

    assert sorted(results) == [False, True]
    assert all(not thread.is_alive() for thread in threads)
    controller.release(groups[0])


def test_partial_conflict_acquisition_is_rolled_back() -> None:
    controller = TaskConflictController(distributed_lock=InMemoryDistributedLock())
    held = controller.acquire(
        tenant_id="tenant-1",
        business_id="business-1",
        task_id="held",
        conflict_keys=("b",),
    )
    try:
        controller.acquire(
            tenant_id="tenant-1",
            business_id="business-1",
            task_id="blocked",
            conflict_keys=("a", "b"),
        )
    except RuntimeError:
        retry = controller.acquire(
            tenant_id="tenant-1",
            business_id="business-1",
            task_id="retry",
            conflict_keys=("a",),
        )
        controller.release(retry)
    else:
        raise AssertionError("expected conflict")
    controller.release(held)



def test_task_conflict_renew_extends_all_leases_without_changing_fencing_tokens() -> None:
    lock = InMemoryDistributedLock()
    controller = TaskConflictController(distributed_lock=lock)
    group = controller.acquire(
        tenant_id="tenant-1",
        business_id="business-1",
        task_id="long",
        conflict_keys=("a", "b"),
        ttl_seconds=30,
    )
    original = {lease.resource: lease for lease in group.leases}
    renewed = controller.renew(group, ttl_seconds=120)

    assert {lease.resource for lease in renewed.leases} == set(original)
    for lease in renewed.leases:
        assert lease.fencing_token == original[lease.resource].fencing_token
        assert lease.expires_at > original[lease.resource].expires_at
    controller.release(renewed)


def test_task_conflict_heartbeat_renews_before_expiry() -> None:
    class _CountingLock(InMemoryDistributedLock):
        def __init__(self) -> None:
            super().__init__()
            self.renew_calls = 0

        def renew(self, **kwargs):
            self.renew_calls += 1
            return super().renew(**kwargs)

    lock = _CountingLock()
    controller = TaskConflictController(distributed_lock=lock)
    group = controller.acquire(
        tenant_id="tenant-1",
        business_id="business-1",
        task_id="heartbeat",
        conflict_keys=("ledger",),
        ttl_seconds=30,
    )
    heartbeat = controller.heartbeat(
        group,
        ttl_seconds=30,
        interval_seconds=0.01,
    )
    threading.Event().wait(0.04)
    renewed = heartbeat.close()

    assert lock.renew_calls >= 1
    assert renewed.leases[0].expires_at > group.leases[0].expires_at
    controller.release(renewed)
