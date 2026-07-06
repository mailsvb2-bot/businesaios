from __future__ import annotations

import asyncio
import itertools
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from core.observability.errors import log_exception_throttled
from core.ratelimit.token_bucket import AsyncTokenBucket

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutboundTask:
    # Lower number = higher priority.
    priority: int
    # Monotonic sequence to preserve FIFO within same priority.
    seq: int
    method: str
    chat_id: int | None
    fn: Callable[[], Awaitable[Any]]
    created_ts: float


class AsyncTelegramOutboundQueue:
    """Async outbound queue (single asyncio loop).

    This is an *opt-in* component. The canonical runtime currently uses
    a thread-based queue to keep sync EffectsPort deterministic.
    """

    def __init__(
        self,
        *,
        global_rps: float = 25.0,
        global_burst: int = 25,
        chat_rps: float = 1.0,
        chat_burst: int = 1,
        maxsize: int = 10_000,
    ) -> None:
        self._log = logging.getLogger(__name__)
        self._global = AsyncTokenBucket(rps=global_rps, burst=global_burst)
        self._chat_rps = float(chat_rps)
        self._chat_burst = int(chat_burst)
        self._per_chat: dict[int, AsyncTokenBucket] = {}
        self._q: asyncio.PriorityQueue[tuple[int, int, OutboundTask]] = asyncio.PriorityQueue(maxsize=maxsize)
        self._stop = asyncio.Event()
        self._seq = itertools.count(1)

        # lightweight metrics (in-loop)
        self._submitted = 0
        self._executed = 0
        self._errors = 0
        self._last_err_ms: dict[str, int] = {}

    def metrics_snapshot(self) -> dict[str, Any]:
        return {
            "submitted": int(self._submitted),
            "executed": int(self._executed),
            "errors": int(self._errors),
        }

    def _throttled_err(self, key: str, e: Exception) -> None:
        now_ms = int(time.time() * 1000)
        last = int(self._last_err_ms.get(key, 0))
        # default: once per 10s per key
        if (now_ms - last) < 10_000:
            return
        self._last_err_ms[key] = now_ms
        self._log.warning("async_outbound_error key=%s err=%s", str(key), e.__class__.__name__)

        # NOTE: do not reset metrics here; errors are useful diagnostics.

    def stop(self) -> None:
        self._stop.set()

    def _bucket_for(self, chat_id: int) -> AsyncTokenBucket:
        b = self._per_chat.get(chat_id)
        if b is None:
            b = AsyncTokenBucket(rps=self._chat_rps, burst=self._chat_burst)
            self._per_chat[chat_id] = b
        return b

    async def submit(self, method: str, chat_id: int | None, fn: Callable[[], Awaitable[Any]], *, priority: int = 50) -> None:
        task = OutboundTask(
            priority=int(priority),
            seq=int(next(self._seq)),
            method=str(method),
            chat_id=int(chat_id) if chat_id is not None else None,
            fn=fn,
            created_ts=time.monotonic(),
        )
        await self._q.put((task.priority, task.seq, task))
        self._submitted += 1

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                _, _, task = await asyncio.wait_for(self._q.get(), timeout=0.25)
            except TimeoutError:
                continue
            try:
                await self._execute_task(task)
            except Exception as e:
                # Never let one bad task kill the outbound loop.
                self._errors += 1
                self._throttled_err(f"task_failed:{task.method}", e)
            finally:
                self._q.task_done()

    async def _execute_task(self, task: OutboundTask) -> None:
        # rate limiting: global + per-chat
        if not self._global.take(1.0):
            await asyncio.sleep(0.02)
            await self._q.put((task.priority, task.seq, task))
            return

        if task.chat_id is not None:
            bucket = self._bucket_for(task.chat_id)
            if not bucket.take(1.0):
                await asyncio.sleep(0.05)
                await self._q.put((task.priority, task.seq, task))
                return

        try:
            await task.fn()
            self._executed += 1
        except Exception:
            self._errors += 1
            log_exception_throttled(
                log,
                key=f"tg.outbound.task:{task.method}",
                msg="telegram outbound: task failed",
                throttle_ms=10_000,
                extra={"method": task.method, "chat_id": task.chat_id},
            )
