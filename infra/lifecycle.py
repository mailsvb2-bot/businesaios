from __future__ import annotations

from dataclasses import dataclass, field

from infra.lifecycle_state import LifecycleState


@dataclass
class ApplicationLifecycle:
    _state: LifecycleState = field(default=LifecycleState.CREATED)

    @property
    def state(self) -> LifecycleState:
        return self._state

    def mark_starting(self) -> None:
        self._state = LifecycleState.STARTING

    def mark_running(self) -> None:
        self._state = LifecycleState.RUNNING

    def mark_stopping(self) -> None:
        self._state = LifecycleState.STOPPING

    def mark_stopped(self) -> None:
        self._state = LifecycleState.STOPPED
