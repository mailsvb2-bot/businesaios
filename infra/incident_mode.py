from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IncidentMode:
    _enabled: bool = False
    _incident_id: str | None = None

    def activate(self, *, incident_id: str) -> None:
        self._enabled = True
        self._incident_id = incident_id

    def deactivate(self) -> None:
        self._enabled = False
        self._incident_id = None

    def is_enabled(self) -> bool:
        return self._enabled

    def incident_id(self) -> str | None:
        return self._incident_id
