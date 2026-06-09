from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrafficSignal:
    signal_id: str = ''
    channel: str = ''
    sessions: float = 0.0
