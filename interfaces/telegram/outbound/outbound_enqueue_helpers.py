from __future__ import annotations

from collections.abc import Callable
from typing import Any


def enqueue_best_effort_with_suppression(
    queue_obj: Any,
    *,
    method: str,
    chat_id: int | None,
    fn: Callable[[], Any],
    meta: dict[str, Any] | None,
    priority: int,
    kind: str,
) -> bool:
    if queue_obj._self_heal.is_suppressed():
        with queue_obj._counters_lock:
            queue_obj._dropped_best_effort += 1
        queue_obj._maybe_alert()
        return False
    return queue_obj.enqueue(
        method=method,
        chat_id=chat_id,
        fn=fn,
        meta=dict(meta or {}),
        critical=False,
        priority=int(priority),
        kind=str(kind),
    )


def parse_legacy_task(task: Any, *, default_priority: int) -> tuple[str, Any, Any, dict, bool, int]:
    method = task.method
    chat_id = getattr(task, "chat_id", None)
    fn = task.fn
    meta = dict(getattr(task, "meta", {}) or {})
    critical = bool(getattr(task, "critical", True))
    prio = int(getattr(task, "priority", int(default_priority)))
    return method, chat_id, fn, meta, critical, prio


__all__ = [
    "enqueue_best_effort_with_suppression",
    "parse_legacy_task",
]
