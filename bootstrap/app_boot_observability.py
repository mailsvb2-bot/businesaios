from __future__ import annotations

from dataclasses import dataclass, field

CANON_APP_BOOT_OBSERVABILITY_FINAL_OWNER = True
CANON_APP_BOOT_OBSERVABILITY_DATA_ONLY = True


@dataclass
class AppBootObservability:
    _events: list[str] = field(default_factory=list)

    def record(self, event_name: str) -> None:
        self._events.append(event_name)

    def events(self) -> tuple[str, ...]:
        return tuple(self._events)
