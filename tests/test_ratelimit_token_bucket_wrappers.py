from __future__ import annotations

import asyncio

import pytest

from core.ratelimit.token_bucket import AsyncTokenBucket, SyncTokenBucket


def test_sync_token_bucket_allows_then_blocks() -> None:
    b = SyncTokenBucket(capacity=1, refill_per_s=0.001, subject="t", bucket="b")
    assert b.try_take(1.0) is True
    assert b.try_take(1.0) is False


@pytest.mark.asyncio
async def test_async_token_bucket_acquire_eventually() -> None:
    b = AsyncTokenBucket(rps=50.0, burst=1, subject="t", bucket="b")
    assert b.take(1.0) is True
    await asyncio.wait_for(b.acquire(1.0), timeout=1.0)
