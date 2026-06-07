from __future__ import annotations

"""TelegramOutboundQueue — priority-based async outbound with self-heal.

Architecture (each file = single responsibility):
  outbound_types.py       — OutboundTask, PriorityArg
  outbound_metrics.py     — OutboundMetricsCollector
  outbound_self_heal.py   — SelfHealController, SelfHealConfig
  outbound_priority.py    — OutboundPriorityMixin  (constants + resolution)
  outbound_enqueue_api.py — OutboundEnqueueApiMixin (typed helpers + legacy)
  outbound_worker.py      — OutboundWorkerMixin    (_worker loop internals)
  outbound_alerter.py     — OutboundAlerterMixin   (SLA alert + purge)
  outbound_queue.py       — THIS FILE: lifecycle + enqueue core + metrics ~130 lines
"""

import itertools
import queue
import threading
from typing import Any, Dict, Optional
from collections.abc import Callable

from interfaces.telegram.outbound.outbound_alerter import OutboundAlerterMixin
from interfaces.telegram.outbound.outbound_backpressure import put_task
from interfaces.telegram.outbound.outbound_enqueue_api import OutboundEnqueueApiMixin
from interfaces.telegram.outbound.outbound_lifecycle import start_worker, stop_worker
from interfaces.telegram.outbound.outbound_metrics import OutboundMetricsCollector
from interfaces.telegram.outbound.outbound_priority import OutboundPriorityMixin
from interfaces.telegram.outbound.outbound_queue_support import (
    build_queue_item,
    build_queue_metrics_snapshot,
    enqueue_with_warning,
    unwrap_queue_call,
)
from interfaces.telegram.outbound.outbound_self_heal import SelfHealConfig, SelfHealController
from interfaces.telegram.outbound.outbound_self_heal_config import build_self_heal_config
from interfaces.telegram.outbound.outbound_types import OutboundTask, PriorityArg
from interfaces.telegram.outbound.outbound_worker import OutboundWorkerMixin
from interfaces.telegram.outbound.rate_limit import TokenBucket

__all__ = ["TelegramOutboundQueue", "OutboundTask", "PriorityArg"]


class TelegramOutboundQueue(
    OutboundPriorityMixin,
    OutboundEnqueueApiMixin,
    OutboundWorkerMixin,
    OutboundAlerterMixin,
):
    """Outbound queue with rate limits + priority scheduling.

    Priority ladder (recommended):
      0  : spinner/ack   10 : UX   30 : payments   80 : marketing / bulk (best-effort)
    """

    def __init__(
        self,
        *,
        global_rps: float,
        global_burst: int,
        chat_rps: float,
        chat_burst: int,
        max_queue: int,
        warn_queue: int,
        emit_event: Callable[[str, dict[str, Any]], None] | None = None,
        log: Any,
        overflow_policy: str = "block",
        auto_start_on_use: bool = True,
        alert_ux_wait_p95_ms: float = 0.0,
        alert_drop_best_effort: bool = True,
        alert_qsize: int = 0,
        alert_min_interval_s: float = 60.0,
        metrics_logger: Callable[[str], None] | None = None,
        self_heal_enabled: bool = False,
        self_heal_marketing_cooldown_s: float = 60.0,
        self_heal_on_sla: bool = True,
        self_heal_on_qsize: bool = True,
        self_heal_on_drops: bool = False,
        self_heal_purge_enabled: bool = True,
        self_heal_purge_kinds_blacklist: tuple[str, ...] | None = None,
        self_heal_purge_kinds_whitelist: tuple[str, ...] | None = None,
        self_heal_purge_max_items: int = 10000,
    ) -> None:
        self._global = TokenBucket(capacity=int(global_burst), refill_per_s=float(global_rps))
        self._chat_rps = float(chat_rps)
        self._chat_burst = int(chat_burst)
        self._per_chat: dict[int, TokenBucket] = {}

        self._max_queue = max(1, int(max_queue))
        self._slots = threading.BoundedSemaphore(self._max_queue)
        self._q: queue.PriorityQueue[tuple[int, int, OutboundTask]] = queue.PriorityQueue(maxsize=self._max_queue)
        self._seq = itertools.count(0)

        self._metrics = OutboundMetricsCollector(maxlen=5000)
        self._warn_queue = int(max(1, int(warn_queue)))
        self._emit = emit_event or (lambda _et, _pl: None)
        self._log = log
        self._metrics_logger = metrics_logger or (lambda s: self._log.warning("%s", s))

        self._overflow = str(overflow_policy or "block").strip().lower()
        if self._overflow not in {"block", "drop", "degrade"}:
            self._overflow = "block"

        self._auto_start = bool(auto_start_on_use)
        self._thr: threading.Thread | None = None
        self._stop = threading.Event()

        self._alert_ux_wait_p95_ms = float(alert_ux_wait_p95_ms)
        self._alert_drop_best_effort = bool(alert_drop_best_effort)
        self._alert_qsize = int(alert_qsize)
        self._alert_min_interval_ns = int(float(alert_min_interval_s) * 1e9)
        self._next_alert_log_ns = 0
        self._next_queue_high_log_ns = 0

        self._counters_lock = threading.Lock()
        self._dropped_best_effort = 0
        self._requeued_rate_limit = 0
        self._requeued_chat_limit = 0
        self._executed = 0

        sh_cfg = build_self_heal_config(
            enabled=bool(self_heal_enabled),
            cooldown_s=float(self_heal_marketing_cooldown_s),
            on_sla=bool(self_heal_on_sla),
            on_qsize=bool(self_heal_on_qsize),
            on_drops=bool(self_heal_on_drops),
            purge_enabled=bool(self_heal_purge_enabled),
            purge_max_items=int(self_heal_purge_max_items),
            purge_blacklist=self_heal_purge_kinds_blacklist,
            purge_whitelist=self_heal_purge_kinds_whitelist,
        )
        self._self_heal = SelfHealController(config=sh_cfg, emit=self._emit)
        self._done_event_factory = threading.Event

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        start_worker(self)

    def stop(self, *, timeout_s: float = 2.0) -> None:
        stop_worker(self, timeout_s=timeout_s)

    # ------------------------------------------------------------------
    # Core enqueue + call  (typed helpers live in OutboundEnqueueApiMixin)
    # ------------------------------------------------------------------

    def enqueue(
        self,
        *,
        method: str,
        chat_id: int | None,
        fn: Callable[[], Any],
        meta: dict[str, Any] | None = None,
        critical: bool = True,
        priority: PriorityArg = 50,
        kind: str = "normal",
    ) -> bool:
        pr, seq, task, _done, _box = build_queue_item(
            queue_obj=self,
            method=method,
            chat_id=chat_id,
            fn=fn,
            meta=meta,
            critical=critical,
            priority=priority,
            kind=kind,
            with_result=False,
        )
        return enqueue_with_warning(
            queue_obj=self,
            method=method,
            meta=meta,
            build_item=(pr, seq, task),
            task=task,
        )

    def call(
        self,
        *,
        method: str,
        chat_id: int | None,
        fn: Callable[[], Any],
        meta: dict[str, Any] | None = None,
        timeout_s: float = 30.0,
        critical: bool = True,
        priority: PriorityArg = 50,
        kind: str = "normal",
    ) -> Any:
        pr, seq, task, done, box = build_queue_item(
            queue_obj=self,
            method=method,
            chat_id=chat_id,
            fn=fn,
            meta=meta,
            critical=critical,
            priority=priority,
            kind=kind,
            with_result=True,
        )
        ok = enqueue_with_warning(
            queue_obj=self,
            method=method,
            meta=meta,
            build_item=(pr, seq, task),
            task=task,
        )
        if not ok:
            return {"ok": False, "dropped": True}
        return unwrap_queue_call(method=method, done=done, box=box, timeout_s=float(timeout_s))

    def _put(self, item: tuple, task: OutboundTask) -> bool:
        return put_task(self, item, task)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def metrics_snapshot(self) -> dict:
        return build_queue_metrics_snapshot(queue_obj=self)
