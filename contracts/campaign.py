from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Campaign:
    campaign_id: str = ''
    channel: str = ''
    budget: float = 0.0
