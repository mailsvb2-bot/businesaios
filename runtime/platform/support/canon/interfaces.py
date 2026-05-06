from __future__ import annotations

from typing import Protocol


class Named(Protocol):
    @property
    def name(self) -> str:
        ...

__all__ = [
    "Named",
]
