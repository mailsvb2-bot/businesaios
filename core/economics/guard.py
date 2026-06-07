from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import GuardSeverity


@dataclass(frozen=True)
class GuardTrigger:
    code: str
    severity: GuardSeverity
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_blocking(self) -> bool:
        return self.severity == GuardSeverity.BLOCK
