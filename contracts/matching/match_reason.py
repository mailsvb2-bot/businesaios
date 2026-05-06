from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class MatchReason:
    code: str = ""
    message: str = ""
    weight: float = 0.0
