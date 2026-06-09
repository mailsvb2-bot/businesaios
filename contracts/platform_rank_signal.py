from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformRankSignal:
    platform: str = ''
    rank: float = 0.0
    delta: float = 0.0
