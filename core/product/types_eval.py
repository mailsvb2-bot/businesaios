from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GuardVerdict:
    allowed: bool
    code: str
    message: str


@dataclass(frozen=True)
class EvaluationResult:
    name: str
    value: float
    details: dict[str, float] = field(default_factory=dict)
