from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SafetyControlViolation(RuntimeError):
    control: str
    reason: str
    details: Mapping[str, Any]

    def __str__(self) -> str:
        return f"{self.control}:{self.reason}"
