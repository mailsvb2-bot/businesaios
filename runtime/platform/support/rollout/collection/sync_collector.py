from __future__ import annotations

class SyncCollector:
    def collect_many(self, callables):
        return [callable_() for callable_ in callables]

__all__ = [
    "SyncCollector",
]
