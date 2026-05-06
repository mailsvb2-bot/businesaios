from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SettingsValue:
    tenant_id: str
    key: str
    value: Any
