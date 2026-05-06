from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ShutdownHooks:
    _hooks: list[Callable[[], None]] = field(default_factory=list)

    def register(self, hook: Callable[[], None]) -> None:
        self._hooks.append(hook)

    def run_all(self) -> None:
        for hook in reversed(self._hooks):
            hook()
