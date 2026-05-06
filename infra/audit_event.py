from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    event_name: str
    actor: str
    category: str
    payload: dict[str, Any] = field(default_factory=dict)
