from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskScore:
    value: float
    reasons: tuple[str, ...]
