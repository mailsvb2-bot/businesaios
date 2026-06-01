from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LeadSource:
    source_name: str = ''
    channel: str = ''
    cost_hint: float = 0.0
