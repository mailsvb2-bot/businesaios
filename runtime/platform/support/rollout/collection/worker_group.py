from __future__ import annotations

class WorkerGroup:
    def __init__(self, workers) -> None:
        self._workers = list(workers)

    def all(self):
        return tuple(self._workers)

__all__ = [
    "WorkerGroup",
]
