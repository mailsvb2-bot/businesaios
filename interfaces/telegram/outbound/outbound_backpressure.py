from __future__ import annotations

import queue
from typing import Any

from core.observability.silent import swallow


def put_task(queue_obj: Any, item: tuple, task: Any) -> bool:
    policy = queue_obj._overflow
    if policy == "block" or (policy == "degrade" and task.critical):
        queue_obj._slots.acquire(True)
        try:
            queue_obj._q.put(item, block=True)
            return True
        except Exception:
            try:
                queue_obj._slots.release()
            except Exception:
                swallow(__name__, "outbound_backpressure.put_task.release")
            raise
    acquired = queue_obj._slots.acquire(False)
    if not acquired:
        _emit_drop(queue_obj, task)
        return False
    try:
        queue_obj._q.put(item, block=False)
        return True
    except queue.Full:
        try:
            queue_obj._slots.release()
        except Exception:
            swallow(__name__, "outbound_backpressure.put_task.full.release")
        _emit_drop(queue_obj, task)
        return False


def _emit_drop(queue_obj: Any, task: Any) -> None:
    with queue_obj._counters_lock:
        queue_obj._dropped_best_effort += 1
    queue_obj._emit(
        "telegram_outbound_dropped",
        {"method": task.method, "qsize": int(queue_obj._q.qsize()), "priority": int(task.priority), **(task.meta or {})},
    )
    queue_obj._maybe_alert()
