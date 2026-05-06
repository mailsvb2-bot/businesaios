from __future__ import annotations

"""Async outbound queue adapter.

P0 goal: the runtime should not be bottlenecked by Telegram API latency.

The codebase historically used a thread-based queue (TelegramOutboundQueue)
with a synchronous interface.

This adapter lets the runtime keep the same sync interface while executing
tasks on an asyncio loop backed by :class:`AsyncTelegramOutboundQueue`.
"""

import asyncio
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from interfaces.telegram.outbound.async_outbound_queue import AsyncTelegramOutboundQueue


class AsyncTelegramOutboundQueueAdapter:
    """Sync-compatible facade over AsyncTelegramOutboundQueue."""

    def __init__(
        self,
        *,
        global_rps: float = 25.0,
        global_burst: int = 25,
        chat_rps: float = 1.0,
        chat_burst: int = 1,
        maxsize: int = 10_000,
        auto_start: bool = True,
    ) -> None:
        self._log = logging.getLogger(__name__)
        self._q = AsyncTelegramOutboundQueue(
            global_rps=global_rps,
            global_burst=global_burst,
            chat_rps=chat_rps,
            chat_burst=chat_burst,
            maxsize=maxsize,
        )
        self._auto_start = bool(auto_start)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thr: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()

        # lightweight metrics
        self._submitted = 0
        self._errors = 0
        self._dropped = 0
        self._last_err_ms: Dict[str, int] = {}

    def _throttled_err(self, key: str, e: Exception) -> None:
        now_ms = int(time.time() * 1000)
        last = int(self._last_err_ms.get(key, 0))
        if (now_ms - last) < 10_000:
            return
        self._last_err_ms[key] = now_ms
        self._log.warning("tg_outbound_adapter_error key=%s err=%s", str(key), e.__class__.__name__)

    @staticmethod
    def _coerce_priority(priority: Any) -> int:
        """Normalize priority to an int.

        Canonical convention:
          - lower number => higher priority
          - string aliases supported for legacy callers
        """
        if isinstance(priority, int):
            return int(priority)
        if isinstance(priority, float):
            return int(priority)
        if isinstance(priority, str):
            p = priority.strip().lower()
            if p in {"high", "p0", "urgent"}:
                return 10
            if p in {"normal", "default", "p1"}:
                return 50
            if p in {"low", "bulk", "p2"}:
                return 90
            try:
                return int(p)
            except Exception:
                return 50
        return 50

    def start(self) -> None:
        if self._thr is not None:
            return

        def _runner() -> None:
            loop = asyncio.new_event_loop()
            self._loop = loop
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._q.run())
            finally:
                try:
                    loop.stop()
                except Exception as e:
                    self._throttled_err("loop_stop", e)
                try:
                    loop.close()
                except Exception as e:
                    self._throttled_err("loop_close", e)

        self._thr = threading.Thread(target=_runner, name="tg-outbound-async", daemon=True)
        self._thr.start()

    def stop(self, *, timeout_s: float = 2.0) -> None:
        try:
            self._q.stop()
        except Exception as e:
            self._throttled_err("queue_stop", e)
        thr = self._thr
        if thr is not None:
            try:
                thr.join(timeout=float(timeout_s))
            except Exception as e:
                self._throttled_err("thread_join", e)
        self._thr = None
        self._loop = None

    def metrics_snapshot(self) -> Dict[str, Any]:
        return {
            "mode": "async",
            "submitted": int(self._submitted),
            "errors": int(self._errors),
            "dropped": int(self._dropped),
            "queue": self._q.metrics_snapshot(),
        }

    def enqueue(
        self,
        *,
        method: str,
        chat_id: Optional[int],
        fn: Callable[[], Any],
        meta: Optional[Dict[str, Any]] = None,
        critical: bool = True,
        priority: int = 50,
        kind: str = "normal",
    ) -> bool:
        if self._thr is None and self._auto_start:
            self.start()

        loop = self._loop
        if loop is None:
            # not started; best-effort behavior depends on criticality
            if bool(critical) is True:
                try:
                    _ = fn()
                    self._submitted += 1
                    return True
                except Exception as e:
                    self._errors += 1
                    self._throttled_err("direct_call_failed", e)
                    return False
            self._dropped += 1
            return False

        async def _wrap() -> Any:
            return fn()

        try:
            fut = asyncio.run_coroutine_threadsafe(
                self._q.submit(
                    method=str(method),
                    chat_id=chat_id,
                    fn=_wrap,
                    priority=self._coerce_priority(priority),
                ),
                loop,
            )
            fut.result(timeout=2.0)
            self._submitted += 1
            return True
        except Exception as e:
            self._errors += 1
            self._throttled_err(f"enqueue_failed:{method}", e)
            return False

    def call(
        self,
        *,
        method: str,
        chat_id: Optional[int],
        fn: Callable[[], Any],
        meta: Optional[Dict[str, Any]] = None,
        timeout_s: float = 30.0,
        critical: bool = True,
        priority: int = 50,
        kind: str = "normal",
    ) -> Any:
        # For sync call semantics, execute directly (critical paths).
        # This preserves determinism for flows that need immediate result.
        return fn()
