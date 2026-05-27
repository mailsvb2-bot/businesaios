from __future__ import annotations


class TransitionEmitter:
    def emit(self, trajectory):
        return list(trajectory.transitions)

__all__ = [
    "TransitionEmitter",
]
