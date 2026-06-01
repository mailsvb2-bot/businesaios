from __future__ import annotations

import logging
import queue
import time
from typing import Any, Callable

from core.observability.errors import log_exception_throttled
from core.observability.silent import swallow
from interfaces.telegram.outbound.outbound_self_heal_payloads import self_heal_payload

log = logging.getLogger(__name__)


def maybe_self_heal(
    *,
    enabled: bool,
    cond_sla: bool,
    cond_drop: bool,
    cond_q: bool,
    on_sla: bool,
    on_qsize: bool,
    on_drops: bool,
    now_ns: int,
    cooldown_ns: int,
    suppressed_until_ns: int,
    purge_enabled: bool,
    set_suppressed_until: Callable[[int], None],
    request_purge: Callable[[], None],
    emit: Callable[[str, dict], None],
    reason: str,
    qsize: int,
    ux_p95_wait: float,
    dropped: int,
) -> None:
    if not enabled:
        return
    should = ((cond_sla and on_sla) or (cond_q and on_qsize) or (cond_drop and on_drops))
    if not should:
        return

    new_until = int(now_ns) + int(cooldown_ns)
    if new_until <= int(suppressed_until_ns):
        return

    set_suppressed_until(new_until)
    if purge_enabled:
        request_purge()

    try:
        now_ms = int(time.time() * 1000)
        emit(
            "telegram_outbound_self_heal",
            self_heal_payload(
                reason=str(reason),
                cooldown_ms=int(cooldown_ns / 1e6),
                suppressed_until_ms=now_ms + int(cooldown_ns / 1e6),
                qsize=int(qsize),
                ux_p95_wait=float(ux_p95_wait),
                dropped=int(dropped),
                timestamp_ms=now_ms,
            ),
        )
    except Exception as exc:
        log_exception_throttled(log, "telegram_outbound_self_heal_emit_failed", exc)


def purge_backlog(
    *,
    q: Any,
    slots: Any,
    counters_lock: Any,
    dropped_counter: list,
    purge_blacklist: tuple,
    purge_whitelist: tuple,
    max_items: int,
    emit: Callable[[str, dict], None],
) -> None:
    kept: list = []
    dropped_n = 0
    scanned = 0

    while True:
        if max_items and scanned >= max_items:
            break
        try:
            item = q.get_nowait()
        except queue.Empty:
            break

        scanned += 1
        _prio, _seq, task = item
        if getattr(task, "method", "") in {"__stop__", "noop"}:
            kept.append(item)
            _safe_task_done(q)
            continue

        is_best_effort = not bool(getattr(task, "critical", True))
        kind = str(getattr(task, "kind", "normal") or "normal").strip().lower()
        should_drop = is_best_effort and (kind in purge_blacklist) and (kind not in purge_whitelist)

        if should_drop:
            dropped_n += 1
            with counters_lock:
                dropped_counter[0] += 1
            try:
                slots.release()
            except Exception:
                swallow(__name__, "purge.slots_release")
            _safe_task_done(q)
            continue

        kept.append(item)
        _safe_task_done(q)

    for item in kept:
        try:
            q.put_nowait(item)
        except Exception:
            swallow(__name__, "purge.reinsert")

    if dropped_n > 0:
        try:
            emit(
                "telegram_outbound_self_heal",
                {
                    "action": "purge_backlog",
                    "dropped": int(dropped_n),
                    "scanned": int(scanned),
                    "blacklist": list(purge_blacklist),
                    "whitelist": list(purge_whitelist),
                    "timestamp_ms": int(time.time() * 1000),
                },
            )
        except Exception as exc:
            log_exception_throttled(log, "telegram_outbound_backlog_purge_emit_failed", exc)


def _safe_task_done(q: Any) -> None:
    try:
        q.task_done()
    except Exception:
        swallow(__name__, "task_done")


__all__ = [
    "maybe_self_heal",
    "purge_backlog",
]
