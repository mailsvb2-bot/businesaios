"""Publisher protocols for knowledge domain."""
from __future__ import annotations

from typing import Protocol

__all__ = ["EventPublisher"]


class EventPublisher(Protocol):
    def publish(self, event: object) -> None: ...
