from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

CANON_BOOT_WIRING_ONLY = True

@dataclass(frozen=True)
class RuntimeWebInfra:
    project_root: Path
    settings_gateway: Any = None
    messaging_policy_read_service: Any = None
    messaging_policy_event_store: Any = None

    @property
    def settings_store(self):
        return self.settings_gateway

    @property
    def messaging_policy_reader(self):
        return self.messaging_policy_read_service

    @property
    def messaging_policy_store(self):
        return self.messaging_policy_event_store
