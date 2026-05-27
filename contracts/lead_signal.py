from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LeadSignal:
    signal_id: str = ''
    source: str = ''
    lead_count: float = 0.0
