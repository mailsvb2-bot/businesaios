from __future__ import annotations

import asyncio

from shared.asyncio_bridge import run_awaitable_sync


async def _compute(value: int) -> int:
    return value + 1


def test_run_awaitable_sync_without_running_loop() -> None:
    assert run_awaitable_sync(_compute(2)) == 3


def test_run_awaitable_sync_with_running_loop() -> None:
    async def _go() -> int:
        return run_awaitable_sync(_compute(4), thread_name_prefix="test-sync-bridge")

    assert asyncio.run(_go()) == 5
