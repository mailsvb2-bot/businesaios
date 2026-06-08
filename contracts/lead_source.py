from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeadSource:
    source_name: str = ''
    channel: str = ''
    cost_hint: float = 0.0
