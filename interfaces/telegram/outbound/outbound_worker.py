"""Worker loop internals for TelegramOutboundQueue.

Responsibility:
  - _worker()         — main background thread loop
  - _requeue()        — re-insert task back into queue after rate-limit
  - _bucket_for_chat()— per-chat TokenBucket lazy factory
"""

from __future__ import annotations

import queue
import time

from core.observability.silent import swallow
from interfaces.telegram.outbound.outbound_types import OutboundTask
from interfaces.telegram.outbound.outbound_worker_helpers import (
    get_or_create_chat_bucket,
    record_task_metrics,
)
from interfaces.telegram.outbound.rate_limit import TokenBucket


class OutboundWorkerMixin:
    """Background worker loop.

    Requires from host class:
      self._stop       : threading.Event
      self._q          : queue.PriorityQueue
      self._global     : TokenBucket
      self._per_chat   : Dict[int, TokenBucket]
      self._chat_rps   : float
      self._chat_burst : int
      self._counters_lock  : threading.Lock
      self._requeued_rate_limit  : int
      self._requeued_chat_limit  : int
      self._executed   : int
      self._slots      : threading.BoundedSemaphore
      self._metrics    : OutboundMetricsCollector
      self._log        : logger
      self._maybe_alert()
      self._maybe_purge_backlog()
    """

    def _worker(self) -> None:
        try:
            self._log.info("[tg-outbound] worker started")
        except Exception:
            swallow(__name__, "outbound_worker.start_log")

        while True:
            if self._stop.is_set() and self._q.empty():
                return

            self._maybe_purge_backlog()
            try:
                _, __, task = self._q.get(timeout=0.2)
            except queue.Empty:
                self._maybe_alert()
                continue

            start_exec_ns: int | None = None
            release_slot = True
            try:
                if task.method == "__stop__":
                    return
                if not self._global.try_take(1.0):
                    time.sleep(0.01)
                    with self._counters_lock:
                        self._requeued_rate_limit += 1
                    self._requeue(task)
                    release_slot = False
                    self._maybe_alert()
                    continue
                if task.chat_id is not None:
                    b = self._bucket_for_chat(task.chat_id)
                    if not b.try_take(1.0):
                        time.sleep(0.01)
                        with self._counters_lock:
                            self._requeued_chat_limit += 1
                        self._requeue(task)
                        release_slot = False
                        self._maybe_alert()
                        continue
                start_exec_ns = time.monotonic_ns()
                res = task.fn()
                if task.done is not None and task.result_box is not None:
                    task.result_box["result"] = res
                    task.done.set()
                with self._counters_lock:
                    self._executed += 1
            except Exception as e:
                if task.done is not None and task.result_box is not None:
                    task.result_box["error"] = e
                    task.done.set()
                try:
                    self._log.exception("[tg-outbound] task failed: %s", task.method)
                except Exception:
                    swallow(__name__, "outbound_worker.task_failed_log")
            finally:
                if start_exec_ns is not None:
                    try:
                        record_task_metrics(metrics=self._metrics, task=task, start_exec_ns=int(start_exec_ns))
                    except Exception:
                        swallow(__name__, "outbound_worker.metrics_record")
                try:
                    self._q.task_done()
                except Exception:
                    swallow(__name__, "outbound_worker.task_done")
                if task.method != "__stop__" and release_slot:
                    try:
                        self._slots.release()
                    except Exception:
                        swallow(__name__, "outbound_worker.slot_release")
            self._maybe_alert()

    def _requeue(self, task: OutboundTask) -> None:
        """Re-insert a rate-limited task back into the priority queue."""
        item = (int(task.priority), int(task.seq), task)
        try:
            self._q.put(item, block=False)
        except queue.Full:
            if task.critical:
                try:
                    self._q.put(item, block=True, timeout=0.5)
                except Exception:
                    swallow(__name__, "outbound_worker._requeue.critical")

    def _bucket_for_chat(self, chat_id: int) -> TokenBucket:
        """Lazily create and cache a per-chat rate-limit bucket."""
        return get_or_create_chat_bucket(
            per_chat=self._per_chat,
            chat_id=int(chat_id),
            chat_burst=int(self._chat_burst),
            chat_rps=float(self._chat_rps),
        )
