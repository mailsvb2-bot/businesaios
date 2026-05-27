from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RevenueSignal:
    signal_id: str = ''
    channel: str = ''
    revenue: float = 0.0
