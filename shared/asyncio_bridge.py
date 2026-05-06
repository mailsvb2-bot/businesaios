from __future__ import annotations

"""Canonical sync/async bridge.

This module is the single place where synchronous entrypoints are allowed to run
an awaitable. It prevents silent divergence between different ad-hoc wrappers
scattered across boot/runtime/marketing code.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, TypeVar
import asyncio

T = TypeVar("T")


def run_awaitable_sync(awaitable: Awaitable[T], *, thread_name_prefix: str = "businesaios-sync-bridge") -> T:
    """Run an awaitable from sync code in a single canonical way.

    Rules:
    - if no loop is running in the current thread -> use ``asyncio.run``
    - if a loop is already running -> execute in a worker thread with its own loop

    The worker-thread path keeps sync surfaces deterministic under tests, CLI,
    and already-running async runtimes.
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    def _runner() -> T:
        return asyncio.run(awaitable)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix=str(thread_name_prefix or "businesaios-sync-bridge")) as pool:
        return pool.submit(_runner).result()


__all__ = ["run_awaitable_sync"]
