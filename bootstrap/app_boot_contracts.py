from __future__ import annotations

from typing import Protocol


class BootableComponent(Protocol):
    def boot(self) -> object:
        ...
