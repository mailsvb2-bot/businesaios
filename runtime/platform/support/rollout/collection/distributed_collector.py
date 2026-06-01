from __future__ import annotations


class DistributedCollector:
    def collect_many(self, workers, request):
        return [worker.collect(request) for worker in workers]

__all__ = [
    "DistributedCollector",
]
