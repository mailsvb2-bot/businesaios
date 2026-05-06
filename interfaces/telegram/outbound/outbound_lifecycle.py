from __future__ import annotations

import threading
import time
from typing import Any

from interfaces.telegram.outbound.outbound_types import OutboundTask
from core.observability.silent import swallow


def ensure_queue_active(queue_obj: Any) -> None:
    if queue_obj._stop.is_set():
        raise RuntimeError("Outbound queue is stopping")
    if queue_obj._thr is None and bool(queue_obj._auto_start):
        start_worker(queue_obj)


def start_worker(queue_obj: Any) -> None:
    if queue_obj._thr is not None:
        try:
            if queue_obj._thr.is_alive():
                return
        except Exception:
            return
        queue_obj._thr = None
    queue_obj._thr = threading.Thread(target=queue_obj._worker, name="tg-outbound-worker", daemon=True)
    queue_obj._thr.start()


def stop_worker(queue_obj: Any, *, timeout_s: float = 2.0) -> None:
    queue_obj._stop.set()
    try:
        seq = int(next(queue_obj._seq))
        item = (
            queue_obj.PRIO_ACK,
            seq,
            OutboundTask(
                priority=queue_obj.PRIO_ACK,
                seq=seq,
                enqueue_t_ns=time.monotonic_ns(),
                kind="system",
                method="__stop__",
                chat_id=None,
                fn=lambda: None,
                created_at=time.monotonic(),
                meta={},
                critical=True,
            ),
        )
        try:
            queue_obj._q.put_nowait(item)
        except Exception:
            queue_obj._q.put(item, block=True, timeout=0.2)
    except Exception:
        swallow(__name__, "outbound_lifecycle.stop_worker")
    if queue_obj._thr is not None:
        try:
            queue_obj._thr.join(timeout=float(timeout_s))
        except Exception:
            swallow(__name__, "outbound_lifecycle.stop_worker.join")
