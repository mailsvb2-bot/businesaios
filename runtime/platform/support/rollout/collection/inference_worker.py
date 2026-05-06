from __future__ import annotations

class InferenceWorker:
    def __init__(self, engine) -> None:
        self._engine = engine

    def act(self, observation):
        return self._engine.infer(observation)

__all__ = [
    "InferenceWorker",
]
