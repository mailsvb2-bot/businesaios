from __future__ import annotations

from enum import Enum


class RuntimeLifecycle(str, Enum):
    CREATED = "created"
    REGISTERING = "registering"
    SEALED = "sealed"


class Lifecycle:
    """Additive lifecycle helper for merged runtime orchestrator patches."""

    def __init__(self, state) -> None:
        self._state = state

    def mark_booted(self) -> None:
        setattr(self._state, "booted", True)

    def mark_ready(self) -> None:
        setattr(self._state, "ready", True)
