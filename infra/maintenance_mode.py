from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MaintenanceMode:
    _enabled: bool = False
    _reason: str | None = None

    def enable(self, *, reason: str | None = None) -> None:
        self._enabled = True
        self._reason = reason

    def disable(self) -> None:
        self._enabled = False
        self._reason = None

    def is_enabled(self) -> bool:
        return self._enabled

    def reason(self) -> str | None:
        return self._reason
