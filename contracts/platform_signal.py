from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlatformSignal:
    signal_id: str = ''
    platform: str = ''
    rank_score: str = ''
