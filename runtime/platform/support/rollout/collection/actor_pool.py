from __future__ import annotations


class ActorPool:
    def __init__(self, workers) -> None:
        self._workers = list(workers)

    def workers(self):
        return tuple(self._workers)

__all__ = [
    "ActorPool",
]
