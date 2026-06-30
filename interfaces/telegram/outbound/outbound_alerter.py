"""SLA alerting and backlog-purge logic for TelegramOutboundQueue.

Responsibility:
  - _maybe_alert()         — check SLA thresholds and emit alert events
  - _maybe_purge_backlog() — drain best-effort tasks on self-heal trigger
"""

from __future__ import annotations

import queue
import time
from core.observability.silent import swallow
from interfaces.telegram.outbound.outbound_alert_helpers import (
    build_alert_event_payload,
    build_alert_reason,
    format_bucket_metrics,
)

class OutboundAlerterMixin:
    """SLA alerting and self-heal backlog purge.

    Requires from host class:
      self._alert_ux_wait_p95_ms  : float
      self._alert_drop_best_effort: bool
      self._alert_qsize           : int
      self._alert_min_interval_ns : int
      self._next_alert_log_ns     : int  (read/write)
      self._next_queue_high_log_ns: int  (read/write)
      self._counters_lock         : threading.Lock
      self._dropped_best_effort   : int  (read/write)
      self._requeued_rate_limit   : int  (read/write)
      self._requeued_chat_limit   : int  (read/write)
      self._executed              : int  (read/write)
      self._q                     : queue.PriorityQueue
      self._slots                 : threading.BoundedSemaphore
      self._self_heal             : SelfHealController
      self._metrics_logger        : Callable[[str], None]
      self._emit                  : Callable[[str, dict], None]
      self.metrics_snapshot()
      self._priority_label()
    """

    # ------------------------------------------------------------------
    # Alert
    # ------------------------------------------------------------------

    def _maybe_alert(self) -> None:
        if (
            self._alert_ux_wait_p95_ms <= 0
            and not self._alert_drop_best_effort
            and self._alert_qsize <= 0
        ):
            return
        now_ns = time.monotonic_ns()
        if now_ns < self._next_alert_log_ns:
            return

        try:
            qsize = int(self._q.qsize())
        except Exception:
            qsize = 0

        with self._counters_lock:
            dropped = int(self._dropped_best_effort)
            rq_glob = int(self._requeued_rate_limit)
            rq_chat = int(self._requeued_chat_limit)
            executed = int(self._executed)

        snap = self.metrics_snapshot()
        ux = snap.get("by_priority", {}).get("ux")
        mkt = snap.get("by_priority", {}).get("marketing")

        ux_p95_wait = float((ux or {}).get("wait_ms", {}).get("p95") or 0.0)
        cond_sla = self._alert_ux_wait_p95_ms > 0 and ux_p95_wait > self._alert_ux_wait_p95_ms
        cond_drop = self._alert_drop_best_effort and dropped > 0
        cond_q = self._alert_qsize > 0 and qsize > self._alert_qsize

        if not (cond_sla or cond_drop or cond_q):
            return

        self._next_alert_log_ns = now_ns + self._alert_min_interval_ns

        reason_s = build_alert_reason(
            cond_sla=cond_sla,
            cond_drop=cond_drop,
            cond_q=cond_q,
            alert_ux_wait_p95_ms=float(self._alert_ux_wait_p95_ms),
            alert_qsize=int(self._alert_qsize),
        )

        self._self_heal.maybe_trigger(
            now_ns=now_ns,
            cond_sla=cond_sla,
            cond_drop=cond_drop,
            cond_q=cond_q,
            reason=reason_s,
            qsize=qsize,
            ux_p95_wait=ux_p95_wait,
            dropped=dropped,
        )

        try:
            self._emit(
                "telegram_outbound_alert",
                build_alert_event_payload(
                    reason=reason_s,
                    qsize=qsize,
                    executed=executed,
                    dropped=dropped,
                    rq_glob=rq_glob,
                    rq_chat=rq_chat,
                    ux=ux or {},
                    mkt=mkt or {},
                ),
            )
        except Exception:
            swallow(__name__, "outbound_alerter._maybe_alert.emit")

        line = (
            f"[outbound][ALERT:{reason_s}] q={qsize} exec={executed} "
            f"drop_best_effort={dropped} requeue_global={rq_glob} requeue_chat={rq_chat} "
            f"UX({format_bucket_metrics(ux)}) MKT({format_bucket_metrics(mkt)})"
        )
        with self._counters_lock:
            self._dropped_best_effort = 0
            self._requeued_rate_limit = 0
            self._requeued_chat_limit = 0
            self._executed = 0
        try:
            self._metrics_logger(line)
        except Exception:
            swallow(__name__, "outbound_alerter._maybe_alert.log")

    # ------------------------------------------------------------------
    # Purge backlog (needs direct _q access, so lives here next to alert)
    # ------------------------------------------------------------------

    def _maybe_purge_backlog(self) -> None:
        """Drain best-effort backlog tasks if SelfHealController requested it."""
        if not self._self_heal.take_purge_request():
            return

        cfg = self._self_heal._cfg
        kept: list = []
        dropped_n = 0
        scanned = 0
        max_items = max(0, cfg.purge_max_items)

        while True:
            if max_items and scanned >= max_items:
                break
            try:
                item = self._q.get_nowait()
            except queue.Empty:
                break
            scanned += 1
            prio, seq, task = item

            if getattr(task, "method", "") in {"__stop__", "noop"}:
                kept.append(item)
                try:
                    self._q.task_done()
                except Exception:
                    swallow(__name__, "outbound_alerter._purge.sentinel_done")
                continue

            is_best_effort = not bool(getattr(task, "critical", True))
            kind = str(getattr(task, "kind", "normal") or "normal").strip().lower()
            in_whitelist = kind in cfg.purge_whitelist
            in_blacklist = kind in cfg.purge_blacklist
            should_drop = is_best_effort and in_blacklist and not in_whitelist

            if should_drop:
                dropped_n += 1
                with self._counters_lock:
                    self._dropped_best_effort += 1
                try:
                    self._slots.release()
                except Exception:
                    swallow(__name__, "outbound_alerter._purge.slot_release")
                try:
                    self._q.task_done()
                except Exception:
                    swallow(__name__, "outbound_alerter._purge.task_done")
                continue

            kept.append(item)
            try:
                self._q.task_done()
            except Exception:
                swallow(__name__, "outbound_alerter._purge.kept_done")

        for item in kept:
            try:
                self._q.put_nowait(item)
            except Exception:
                swallow(__name__, "outbound_alerter._purge.reinsert")

        if dropped_n > 0:
            try:
                self._emit("telegram_outbound_self_heal", {
                    "action": "purge_backlog",
                    "dropped": dropped_n, "scanned": scanned,
                    "blacklist": list(cfg.purge_blacklist),
                    "whitelist": list(cfg.purge_whitelist),
                    "timestamp_ms": int(time.time() * 1000),
                })
            except Exception:
                swallow(__name__, "outbound_alerter._purge.emit")
