from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StopDecision:
    stop: bool

__all__ = [
    "StopDecision",
]
