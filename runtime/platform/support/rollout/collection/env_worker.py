from __future__ import annotations


class EnvWorker:
    def __init__(self, env) -> None:
        self._env = env

    def reset(self):
        return self._env.reset()

    def step(self, action):
        return self._env.step(action)

__all__ = [
    "EnvWorker",
]
