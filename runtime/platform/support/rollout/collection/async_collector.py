from __future__ import annotations

import asyncio


class AsyncCollector:
    async def collect_many(self, coroutines):
        return await asyncio.gather(*coroutines)

__all__ = [
    "AsyncCollector",
]
