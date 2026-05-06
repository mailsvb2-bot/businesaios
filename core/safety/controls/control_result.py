from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ControlStatus(str, Enum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"


@dataclass(frozen=True)
class ControlDecision:
    control: str
    status: ControlStatus
    reason: str
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.status == ControlStatus.ALLOW
