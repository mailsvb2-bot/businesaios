from __future__ import annotations

from typing import Any, Dict, Optional
from collections.abc import Callable

from interfaces.telegram.outbound.outbound_call_result import unwrap_call_result
from interfaces.telegram.outbound.outbound_enqueue_warning import maybe_emit_queue_high_warning
from interfaces.telegram.outbound.outbound_lifecycle import ensure_queue_active
from interfaces.telegram.outbound.outbound_task_builders import build_outbound_task


def build_queue_item(*, queue_obj, method: str, chat_id: int | None, fn: Callable[[], Any], meta: dict[str, Any] | None, critical: bool, priority, kind: str, with_result: bool = False):
    pr = int(queue_obj._normalize_priority(priority))
    seq = int(next(queue_obj._seq))
    result_box: dict[str, Any] | None = {} if with_result else None
    done = queue_obj._done_event_factory() if with_result else None
    task = build_outbound_task(
        priority=pr,
        seq=seq,
        kind=kind,
        meta=meta,
        method=method,
        chat_id=chat_id,
        fn=fn,
        done=done,
        result_box=result_box,
        critical=bool(critical),
    )
    return pr, seq, task, done, result_box


def enqueue_with_warning(*, queue_obj, method: str, meta, build_item, task) -> bool:
    ensure_queue_active(queue_obj)
    qsize = int(queue_obj._q.qsize())
    maybe_emit_queue_high_warning(queue_obj, qsize=qsize, method=method, meta=meta)
    return queue_obj._put(build_item, task)


def unwrap_queue_call(*, method: str, done, box, timeout_s: float):
    return unwrap_call_result(method=method, done=done, box=box, timeout_s=float(timeout_s))


def build_queue_metrics_snapshot(*, queue_obj) -> dict:
    snap = queue_obj._metrics.build_snapshot_dict(queue_obj._priority_label)
    try:
        snap["qsize"] = int(queue_obj._q.qsize())
    except Exception:
        snap["qsize"] = 0
    return snap
