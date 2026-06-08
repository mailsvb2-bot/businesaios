from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdSignal:
    signal_id: str = ''
    channel: str = ''
    ctr: float = 0.0
