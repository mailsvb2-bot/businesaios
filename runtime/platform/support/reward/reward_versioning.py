from __future__ import annotations


class RewardVersioning:
    def __init__(self) -> None:
        self._version = 0

    def next(self) -> str:
        self._version += 1
        return str(self._version)

__all__ = [
    "RewardVersioning",
]
