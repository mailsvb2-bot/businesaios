from __future__ import annotations

import threading

from application.task.conflict_control import TaskConflictController
from reliability.distributed_lock import InMemoryDistributedLock


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
